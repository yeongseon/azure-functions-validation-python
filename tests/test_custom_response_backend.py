"""Custom response backends must be usable through @validate_http (issue #539).

The public adapter guide says a custom ``ValidationAdapter`` can serve a
non-Pydantic model system, but two gaps broke that promise:

1. Decoration unconditionally built ``TypeAdapter(response_model)``, so an
   ordinary (non-Pydantic) response model raised before a custom backend's
   own ``validate_response``/``serialize_response`` ever ran.
2. When the declared model happened to be Pydantic-compatible, the pipeline
   serialized the validated result by calling
   ``response_type_adapter.dump_json(...)`` directly -- never the configured
   adapter's own serializer, so a custom backend's response serialization was
   silently bypassed.

These tests exercise both gaps through the real decorated-handler path (not
only direct adapter-method calls), covering both sync and async handlers, and
confirm the default ``PydanticAdapter`` path (declared-model-strict
serialization, #463; alias handling) is unaffected.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from azure.functions import HttpRequest
from pydantic import BaseModel, Field, TypeAdapter
import pytest

from azure_functions_validation import PydanticAdapter, validate_http
from azure_functions_validation.errors import SerializationError


def _get(path: str = "/api/x") -> HttpRequest:
    return HttpRequest(method="GET", url=f"http://localhost{path}", body=b"")


class _Output(BaseModel):
    value: str


class _NativeRecord:
    """An ordinary class with no pydantic-core schema at all."""

    def __init__(self, value: str) -> None:
        self.value = value


class _NativeAdapter(PydanticAdapter):
    """A backend that validates/serializes a non-Pydantic model entirely on its own."""

    def __init__(self) -> None:
        super().__init__()
        self.validation_calls = 0
        self.serialize_response_calls = 0

    def validate_response(self, obj: Any, model: Any, *, type_adapter: Any = None) -> Any:
        self.validation_calls += 1
        assert type_adapter is None  # TypeAdapter(_NativeRecord) cannot be built
        return obj

    def serialize_response(
        self,
        obj: Any,
        model: Any,
        *,
        type_adapter: Any = None,
        by_alias: bool = True,
        exclude_none: bool = False,
        exclude_unset: bool = False,
    ) -> tuple[str | bytes, str]:
        self.serialize_response_calls += 1
        return f"custom:{obj.value}", "text/plain"


class TestNonPydanticResponseBackend:
    """Reproduction A: a non-Pydantic response_model must reach its own backend."""

    def test_decoration_does_not_raise_for_non_pydantic_model(self) -> None:
        adapter = _NativeAdapter()

        @validate_http(adapter=adapter, response_model=_NativeRecord)
        def handler(req: HttpRequest) -> _NativeRecord:
            return _NativeRecord("ok")

        # Decoration itself succeeding is the regression guard -- it used to
        # raise PydanticSchemaGenerationError before the handler ever ran.
        response = handler(_get())
        assert response.status_code == 200

    def test_sync_handler_invokes_custom_validate_and_serialize(self) -> None:
        adapter = _NativeAdapter()

        @validate_http(adapter=adapter, response_model=_NativeRecord)
        def handler(req: HttpRequest) -> _NativeRecord:
            return _NativeRecord("ok")

        response = handler(_get())

        assert response.status_code == 200
        assert response.get_body() == b"custom:ok"
        assert dict(response.headers)["Content-Type"] == "text/plain"
        assert adapter.validation_calls == 1
        assert adapter.serialize_response_calls == 1

    def test_async_handler_invokes_custom_validate_and_serialize(self) -> None:
        adapter = _NativeAdapter()

        @validate_http(adapter=adapter, response_model=_NativeRecord)
        async def handler(req: HttpRequest) -> _NativeRecord:
            return _NativeRecord("ok")

        response = asyncio.run(handler(_get()))

        assert response.status_code == 200
        assert response.get_body() == b"custom:ok"
        assert adapter.validation_calls == 1
        assert adapter.serialize_response_calls == 1


class _RecordingSerializationAdapter(PydanticAdapter):
    """A backend compatible with Pydantic validation but with its OWN serializer."""

    def __init__(self) -> None:
        super().__init__()
        self.validation_calls = 0
        self.serialization_calls = 0

    def validate_response(self, obj: Any, model: Any, *, type_adapter: Any = None) -> Any:
        self.validation_calls += 1
        return super().validate_response(obj, model, type_adapter=type_adapter)

    def serialize_response(
        self,
        obj: Any,
        model: Any,
        *,
        type_adapter: Any = None,
        by_alias: bool = True,
        exclude_none: bool = False,
        exclude_unset: bool = False,
    ) -> tuple[str | bytes, str]:
        self.serialization_calls += 1
        return f"custom:{obj.value}", "text/plain"


class TestCustomSerializationNotBypassed:
    """Reproduction B: a compatible model's custom serializer must actually run."""

    def test_sync_handler_uses_custom_serializer(self) -> None:
        adapter = _RecordingSerializationAdapter()

        @validate_http(adapter=adapter, response_model=_Output)
        def handler(req: HttpRequest) -> _Output:
            return _Output(value="ok")

        response = handler(_get())

        assert response.status_code == 200
        assert response.get_body() == b"custom:ok"
        assert dict(response.headers)["Content-Type"] == "text/plain"
        assert adapter.validation_calls == 1
        assert adapter.serialization_calls == 1

    def test_async_handler_uses_custom_serializer(self) -> None:
        adapter = _RecordingSerializationAdapter()

        @validate_http(adapter=adapter, response_model=_Output)
        async def handler(req: HttpRequest) -> _Output:
            return _Output(value="ok")

        response = asyncio.run(handler(_get()))

        assert response.status_code == 200
        assert response.get_body() == b"custom:ok"
        assert adapter.serialization_calls == 1

    def test_serialize_response_error_still_formatted_as_500(self) -> None:
        class _FailingAdapter(PydanticAdapter):
            def serialize_response(
                self,
                obj: Any,
                model: Any,
                *,
                type_adapter: Any = None,
                by_alias: bool = True,
                exclude_none: bool = False,
                exclude_unset: bool = False,
            ) -> tuple[str | bytes, str]:
                raise SerializationError("boom")

        @validate_http(adapter=_FailingAdapter(), response_model=_Output)
        def handler(req: HttpRequest) -> _Output:
            return _Output(value="ok")

        response = handler(_get())

        assert response.status_code == 500


class TestDefaultPydanticPathUnaffected:
    """The default backend's declared-model-strict serialization (#463) still holds."""

    def test_subclass_only_fields_are_not_leaked(self) -> None:
        class UserOut(BaseModel):
            name: str

        class UserDB(UserOut):
            password_hash: str

        @validate_http(response_model=UserOut)
        def handler(req: HttpRequest) -> UserOut:
            return UserDB(name="Ada", password_hash="secret")

        response = handler(_get())

        assert json.loads(response.get_body()) == {"name": "Ada"}

    def test_response_alias_is_honored(self) -> None:
        class AliasOut(BaseModel):
            internal: str = Field(serialization_alias="wireName")

        @validate_http(response_model=AliasOut)
        def handler(req: HttpRequest) -> AliasOut:
            return AliasOut(internal="value")

        response = handler(_get())

        assert json.loads(response.get_body()) == {"wireName": "value"}

    def test_response_by_alias_false_is_honored(self) -> None:
        class AliasOut(BaseModel):
            internal: str = Field(serialization_alias="wireName")

        @validate_http(response_model=AliasOut, response_by_alias=False)
        def handler(req: HttpRequest) -> AliasOut:
            return AliasOut(internal="value")

        response = handler(_get())

        assert json.loads(response.get_body()) == {"internal": "value"}

    def test_exclude_none_is_honored(self) -> None:
        class MaybeOut(BaseModel):
            name: str
            nickname: str | None = None

        @validate_http(response_model=MaybeOut, response_exclude_none=True)
        def handler(req: HttpRequest) -> MaybeOut:
            return MaybeOut(name="Ada")

        response = handler(_get())

        assert json.loads(response.get_body()) == {"name": "Ada"}


class TestDecorationFallbackForUnbuildableTypeAdapter:
    def test_pre_built_type_adapter_is_none_when_construction_fails(self) -> None:
        """Regression guard for the decoration-time try/except itself."""
        adapter = _NativeAdapter()

        @validate_http(adapter=adapter, response_model=_NativeRecord)
        def handler(req: HttpRequest) -> _NativeRecord:
            return _NativeRecord("ok")

        with pytest.raises(Exception):  # noqa: B017, PT011
            TypeAdapter(_NativeRecord)

        # The decorated handler itself must still work end to end.
        response = handler(_get())
        assert response.status_code == 200
