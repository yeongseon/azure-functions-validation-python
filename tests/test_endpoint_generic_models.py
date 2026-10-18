"""Endpoint metadata for supported generic Pydantic annotations (issue #537).

``build_endpoint_metadata()`` used to gate ``request_body``/``responses`` on
``_is_model_type()``, a direct-``BaseModel``-subclass-only check. The runtime
accepts a much broader, ``TypeAdapter``-backed contract for ``body``/
``response_model`` (``list[Model]``, ``Optional[Model]``, ``Union[...]``,
``Annotated[...]`` -- see #452), so a working typed endpoint using any of
those forms advertised no request body, no validation-error response, and no
typed success response. These tests pin the fix: supported generics now emit
real schemas, a nullable response documents both its non-null success status
and the runtime's actual ``204`` short-circuit for a validated ``None``
result, and a genuinely unsupported/custom-backend annotation stays silently
absent exactly as before (not a crash, not a fabricated schema).
"""

from __future__ import annotations

from typing import Annotated, Any, cast

import azure.functions as func
import jsonschema
from pydantic import BaseModel, Field
import pytest

from azure_functions_validation import validate_http
from azure_functions_validation._endpoint import (
    ENDPOINT_NAMESPACE,
    build_endpoint_metadata,
)
from azure_functions_validation._metadata import METADATA_ATTR
from azure_functions_validation.schemas import assert_defs_present_if_ref_used, load_endpoint_schema

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Item(BaseModel):
    name: str


class OtherItem(BaseModel):
    code: int


class _Config:
    def __init__(self, **kw: Any) -> None:
        self.body = kw.get("body")
        self.query = kw.get("query")
        self.path = kw.get("path")
        self.headers = kw.get("headers")
        self.response_model = kw.get("response_model")
        self.response_by_alias = kw.get("response_by_alias", True)
        self.success_status_code = kw.get("success_status_code", 200)


def _endpoint_of(handler: Any) -> dict[str, Any]:
    meta = getattr(handler, METADATA_ATTR)
    return cast("dict[str, Any]", meta[ENDPOINT_NAMESPACE])


def _validate_envelope(payload: dict[str, Any]) -> None:
    jsonschema.validate(payload, load_endpoint_schema())


# ---------------------------------------------------------------------------
# Issue's own reproduction: list[Item] body + response
# ---------------------------------------------------------------------------


class TestListAnnotationReproduction:
    def test_list_body_and_response_emit_contracts(self) -> None:
        @validate_http(body=list[Item], response_model=list[Item])
        def handler(req: func.HttpRequest, body: Any) -> Any:
            return body

        payload = _endpoint_of(handler)
        _validate_envelope(payload)

        assert payload["request_body"]["type"] == "array"
        assert payload["request_body"]["items"] == {"$ref": "#/$defs/Item"}
        assert "Item" in payload["request_body"]["$defs"]
        assert payload["request_body_required"] is True

        assert set(payload["responses"]) == {"200", "422"}
        response_schema = payload["responses"]["200"]["schema"]
        assert response_schema["type"] == "array"
        assert response_schema["items"] == {"$ref": "#/$defs/Item"}

    def test_list_body_instance_validation(self) -> None:
        @validate_http(body=list[Item], response_model=list[Item])
        def handler(req: func.HttpRequest, body: Any) -> Any:
            return body

        schema = _endpoint_of(handler)["request_body"]
        jsonschema.validate([{"name": "ok"}], schema)
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate([{}], schema)
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate("not a list", schema)


# ---------------------------------------------------------------------------
# Optional[Model] -- request side keeps request_body_required True (#347)
# ---------------------------------------------------------------------------


class TestOptionalBody:
    def test_optional_body_emits_contract_and_stays_required(self) -> None:
        payload = build_endpoint_metadata(_Config(body=Item | None))
        _validate_envelope({"version": 1, **payload})

        assert payload["request_body_required"] is True
        jsonschema.validate({"name": "ok"}, payload["request_body"])
        jsonschema.validate(None, payload["request_body"])

    def test_optional_body_still_triggers_422(self) -> None:
        payload = build_endpoint_metadata(_Config(body=Item | None))
        responses = payload["responses"]
        assert responses is not None
        assert "422" in responses


# ---------------------------------------------------------------------------
# Optional[Model] -- response side splits into non-null success + 204 (#537)
# ---------------------------------------------------------------------------


class TestNullableResponse:
    def test_nullable_response_documents_success_and_204(self) -> None:
        payload = build_endpoint_metadata(_Config(response_model=Item | None))
        responses = payload["responses"]
        assert responses is not None

        assert set(responses) == {"200", "204"}
        success_schema = responses["200"]["schema"]
        # The success-status schema is truthful to what is actually ever
        # serialized under that status: never a null body (that outcome is
        # the separate 204 entry), so "null" must not appear as a top-level
        # accepted shape here.
        assert "anyOf" not in success_schema
        assert success_schema["$ref"] == "#/$defs/Item"
        assert "Item" in success_schema["$defs"]
        assert_defs_present_if_ref_used(success_schema)

        # The 204 entry carries no schema -- it is genuinely bodyless.
        assert responses["204"] == {}

    def test_nullable_response_honors_custom_status_code(self) -> None:
        payload = build_endpoint_metadata(
            _Config(response_model=Item | None, success_status_code=201)
        )
        responses = payload["responses"]
        assert responses is not None
        assert set(responses) == {"201", "204"}

    def test_non_nullable_generic_response_has_no_204(self) -> None:
        payload = build_endpoint_metadata(_Config(response_model=list[Item]))
        responses = payload["responses"]
        assert responses is not None
        assert set(responses) == {"200"}

    def test_nullable_response_instance_validation(self) -> None:
        payload = build_endpoint_metadata(_Config(response_model=Item | None))
        responses = payload["responses"]
        assert responses is not None
        schema = responses["200"]["schema"]
        jsonschema.validate({"name": "ok"}, schema)
        with pytest.raises(jsonschema.ValidationError):
            # The non-null success schema must still reject a payload that
            # does not match Item -- the fix must not widen validation.
            jsonschema.validate({"wrong": "shape"}, schema)


# ---------------------------------------------------------------------------
# Union[Model, Model] -- both positions
# ---------------------------------------------------------------------------


class TestUnionAnnotation:
    def test_union_body_covers_each_member(self) -> None:
        payload = build_endpoint_metadata(_Config(body=Item | OtherItem))
        schema = payload["request_body"]
        assert schema is not None
        assert_defs_present_if_ref_used(schema)
        assert payload["request_body_required"] is True

        jsonschema.validate({"name": "ok"}, schema)
        jsonschema.validate({"code": 1}, schema)
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate({"unrelated": True}, schema)

    def test_union_response_covers_each_member(self) -> None:
        payload = build_endpoint_metadata(_Config(response_model=Item | OtherItem))
        responses = payload["responses"]
        assert responses is not None
        schema = responses["200"]["schema"]
        jsonschema.validate({"name": "ok"}, schema)
        jsonschema.validate({"code": 1}, schema)
        # A plain Union (no None member) must not get a spurious 204.
        assert "204" not in responses


# ---------------------------------------------------------------------------
# Annotated[Model, ...] -- metadata must not be lost, nor crash
# ---------------------------------------------------------------------------


class TestAnnotatedForm:
    def test_annotated_body_resolves_to_model_schema(self) -> None:
        payload = build_endpoint_metadata(
            _Config(body=Annotated[Item, Field(description="an item")])
        )
        schema = payload["request_body"]
        assert schema is not None
        assert schema["$ref"] == "#/$defs/Item"
        assert "Item" in schema["$defs"]
        assert payload["request_body_required"] is True
        jsonschema.validate({"name": "ok"}, schema)


# ---------------------------------------------------------------------------
# Serialization mode + alias policy still honored for generic responses
# ---------------------------------------------------------------------------


class _AliasedItem(BaseModel):
    full_name: str = Field(serialization_alias="fullName")


class TestGenericResponseAliasing:
    def test_list_response_uses_serialization_alias(self) -> None:
        payload = build_endpoint_metadata(_Config(response_model=list[_AliasedItem]))
        responses = payload["responses"]
        assert responses is not None
        item_schema = responses["200"]["schema"]["$defs"]["_AliasedItem"]
        assert "fullName" in item_schema["properties"]
        assert "full_name" not in item_schema["properties"]

    def test_list_response_respects_response_by_alias_false(self) -> None:
        payload = build_endpoint_metadata(
            _Config(response_model=list[_AliasedItem], response_by_alias=False)
        )
        responses = payload["responses"]
        assert responses is not None
        item_schema = responses["200"]["schema"]["$defs"]["_AliasedItem"]
        assert "full_name" in item_schema["properties"]


# ---------------------------------------------------------------------------
# Through the real decorator end to end (not just the builder unit)
# ---------------------------------------------------------------------------


class TestEndToEndThroughDecorator:
    def test_decorator_emits_list_contract_for_real_handler(self) -> None:
        @validate_http(body=list[Item], response_model=list[Item], status_code=201)
        def handler(req: func.HttpRequest, body: Any) -> Any:
            return body

        payload = _endpoint_of(handler)
        _validate_envelope(payload)
        assert set(payload["responses"]) == {"201", "422"}

    def test_decorator_emits_nullable_split_for_real_handler(self) -> None:
        @validate_http(response_model=Item | None)
        def handler(req: func.HttpRequest) -> Any:
            return None

        payload = _endpoint_of(handler)
        _validate_envelope(payload)
        assert set(payload["responses"]) == {"200", "204"}


# ---------------------------------------------------------------------------
# Unsupported/custom-backend annotations stay silently absent, not crashed
# ---------------------------------------------------------------------------


class TestUnsupportedAnnotationsStayAbsent:
    def test_arbitrary_class_without_pydantic_support_is_ignored(self) -> None:
        class NotAModel:
            pass

        payload = build_endpoint_metadata(_Config(body=NotAModel, response_model=NotAModel))
        _validate_envelope({"version": 1, **payload})
        assert payload["request_body"] is None
        assert payload["request_body_required"] is False
        assert payload["responses"] is None

    def test_arbitrary_instance_is_ignored(self) -> None:
        payload = build_endpoint_metadata(_Config(body=object(), response_model=object()))
        assert payload["request_body"] is None
        assert payload["responses"] is None
