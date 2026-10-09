"""Reusable conformance tests for validation-adapter implementations."""

from collections.abc import Callable
from dataclasses import dataclass
import json
from typing import Any

from azure.functions import HttpRequest
from pydantic import BaseModel, ConfigDict, Field

from .adapter import ValidationAdapter
from .errors import AdapterValidationError, MalformedRequestError, SerializationError

__all__ = ["AdapterConformanceTests"]


class _BodyModel(BaseModel):
    name: str
    count: int


class _QueryModel(BaseModel):
    limit: int


class _PathModel(BaseModel):
    item_id: int


class _HeadersModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    request_id: str = Field(alias="X-Request-Id")


class _ResponseModel(BaseModel):
    status: str


@dataclass(frozen=True, slots=True)
class _DataclassPayload:
    value: int


class AdapterConformanceTests:
    """Pytest-agnostic contract tests for :class:`ValidationAdapter`.

    Subclass this mixin in a test module and override :meth:`make_adapter`.
    The default model hooks use Pydantic models; adapters for another model
    system can override the ``*_model`` and valid-value hooks.
    """

    def make_adapter(self) -> ValidationAdapter:
        """Return a fresh adapter under test."""
        raise NotImplementedError

    def body_model(self) -> Any:
        """Return the request-body model used by the suite."""
        return _BodyModel

    def query_model(self) -> Any:
        """Return the query model used by the suite."""
        return _QueryModel

    def path_model(self) -> Any:
        """Return the path model used by the suite."""
        return _PathModel

    def headers_model(self) -> Any:
        """Return the headers model used by the suite."""
        return _HeadersModel

    def response_model(self) -> Any:
        """Return the response model used by the suite."""
        return _ResponseModel

    def valid_body(self) -> dict[str, Any]:
        """Return data accepted by :meth:`body_model`."""
        return {"name": "example", "count": 2}

    def valid_response(self) -> dict[str, Any]:
        """Return data accepted by :meth:`response_model`."""
        return {"status": "ok"}

    @staticmethod
    def _request(
        *,
        body: bytes = b"",
        params: dict[str, str] | None = None,
        route_params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> HttpRequest:
        return HttpRequest(
            method="POST",
            url="http://localhost/api/conformance",
            body=body,
            params=params or {},
            route_params=route_params or {},
            headers=headers or {},
        )

    @staticmethod
    def _assert_validation_error(
        action: Callable[[], Any],
        source: str,
        *,
        error_type: str | None = None,
    ) -> AdapterValidationError:
        try:
            action()
        except AdapterValidationError as exc:
            assert exc.errors  # nosec B101
            for entry in exc.errors:
                assert set(entry) == {"loc", "msg", "type"}  # nosec B101
                assert isinstance(entry["loc"], list)  # nosec B101
                assert isinstance(entry["msg"], str)  # nosec B101
                assert isinstance(entry["type"], str)  # nosec B101
                assert entry["loc"][0] == source  # nosec B101
            if error_type is not None:
                assert exc.errors[0]["type"] == error_type  # nosec B101
            return exc
        raise AssertionError("Expected AdapterValidationError")

    def test_parse_body_accepts_valid_json(self) -> None:
        adapter = self.make_adapter()
        request = self._request(body=json.dumps(self.valid_body()).encode())

        result = adapter.parse_body(request, self.body_model())

        assert result is not None  # nosec B101

    def test_invalid_json_raises_malformed_request_error(self) -> None:
        adapter = self.make_adapter()
        request = self._request(body=b"{invalid")

        try:
            adapter.parse_body(request, self.body_model())
        except MalformedRequestError:
            return
        except Exception as exc:
            raise AssertionError("Expected MalformedRequestError") from exc
        raise AssertionError("Expected MalformedRequestError")

    def test_invalid_utf8_raises_malformed_request_error(self) -> None:
        adapter = self.make_adapter()
        request = self._request(body=b"\x80")

        try:
            adapter.parse_body(request, self.body_model())
        except MalformedRequestError:
            return
        except Exception as exc:
            raise AssertionError("Expected MalformedRequestError") from exc
        raise AssertionError("Expected MalformedRequestError")

    def test_empty_body_raises_missing_validation_error(self) -> None:
        adapter = self.make_adapter()
        request = self._request()

        self._assert_validation_error(
            lambda: adapter.parse_body(request, self.body_model()),
            "body",
            error_type="missing",
        )

    def test_body_schema_mismatch_has_normalized_location(self) -> None:
        adapter = self.make_adapter()
        request = self._request(body=b'{"name":"example","count":"bad"}')

        self._assert_validation_error(
            lambda: adapter.parse_body(request, self.body_model()), "body"
        )

    def test_query_parsing_and_error_location(self) -> None:
        adapter = self.make_adapter()
        valid = adapter.parse_query(self._request(params={"limit": "2"}), self.query_model())
        assert valid is not None  # nosec B101

        self._assert_validation_error(
            lambda: adapter.parse_query(self._request(params={"limit": "bad"}), self.query_model()),
            "query",
        )

    def test_path_parsing_and_error_location(self) -> None:
        adapter = self.make_adapter()
        valid = adapter.parse_path(self._request(route_params={"item_id": "2"}), self.path_model())
        assert valid is not None  # nosec B101

        self._assert_validation_error(
            lambda: adapter.parse_path(
                self._request(route_params={"item_id": "bad"}), self.path_model()
            ),
            "path",
        )

    def test_header_parsing_and_error_location(self) -> None:
        adapter = self.make_adapter()
        valid = adapter.parse_headers(
            self._request(headers={"X-Request-Id": "request-1"}), self.headers_model()
        )
        assert valid is not None  # nosec B101

        self._assert_validation_error(
            lambda: adapter.parse_headers(self._request(), self.headers_model()), "headers"
        )

    def test_validate_response_accepts_valid_value(self) -> None:
        adapter = self.make_adapter()

        result = adapter.validate_response(self.valid_response(), self.response_model())

        assert result is not None  # nosec B101

    def test_validate_response_rejects_invalid_value(self) -> None:
        adapter = self.make_adapter()

        self._assert_validation_error(
            lambda: adapter.validate_response({"unexpected": True}, self.response_model()),
            "response",
        )

    def test_serialize_supported_values(self) -> None:
        adapter = self.make_adapter()
        values = (
            _ResponseModel(status="ok"),
            {"status": "ok"},
            ["ok"],
            "ok",
            b"ok",
            1,
            1.5,
            True,
            _DataclassPayload(value=1),
        )

        for value in values:
            content, content_type = adapter.serialize(value)
            assert isinstance(content, (bytes, str))  # nosec B101
            assert isinstance(content_type, str)  # nosec B101
            assert content_type  # nosec B101

    def test_serialize_rejects_unsupported_value(self) -> None:
        adapter = self.make_adapter()

        try:
            adapter.serialize(AdapterConformanceTests)
        except SerializationError:
            return
        raise AssertionError("Expected SerializationError")

    def test_format_error_returns_json_serializable_detail(self) -> None:
        adapter = self.make_adapter()
        error = AdapterValidationError(
            "invalid",
            [{"loc": ["body", "count"], "msg": "Invalid value", "type": "invalid"}],
        )

        result = adapter.format_error(error)

        assert set(result) == {"detail"}  # nosec B101
        assert isinstance(result["detail"], list)  # nosec B101
        json.dumps(result)
