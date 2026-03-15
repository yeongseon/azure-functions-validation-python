"""Tests for the public API surface of azure-functions-validation v0.5."""

import json
from unittest.mock import Mock

from azure.functions import HttpRequest, HttpResponse
from pydantic import BaseModel, Field
import pytest

import azure_functions_validation
from azure_functions_validation import (
    ErrorFormatter,
    ResponseValidationError,
    validate_http,
)

# ---------------------------------------------------------------------------
# 1. API Surface — only the declared exports exist
# ---------------------------------------------------------------------------


class TestAPISurface:
    """Verify __all__ matches exactly the three public names + __version__."""

    def test_all_exports(self) -> None:
        assert set(azure_functions_validation.__all__) == {
            "__version__",
            "validate_http",
            "ResponseValidationError",
            "ErrorFormatter",
        }

    def test_version_is_0_5_2(self) -> None:
        assert azure_functions_validation.__version__ == "0.5.2"

    def test_validate_http_is_callable(self) -> None:
        assert callable(validate_http)

    def test_response_validation_error_is_exception(self) -> None:
        assert issubclass(ResponseValidationError, Exception)

    def test_error_formatter_is_callable_alias(self) -> None:
        # ErrorFormatter is Callable[[Exception, int], dict[str, Any]]
        assert ErrorFormatter is not None

    def test_removed_exports_are_absent(self) -> None:
        """Symbols removed in v0.4 must not be importable from the package."""
        removed = [
            "register_global_error_handler",
            "clear_global_error_handlers",
            "get_contract_schema",
            "get_request_contract_metadata",
            "get_response_contract_metadata",
            "get_validation_error_contract",
            "describe_validation_contract",
            "generate_422_error_schema",
            "get_validation_error_examples",
            "get_openapi_response_metadata",
            "contract_test",
            "verify_contracts",
        ]
        for name in removed:
            assert not hasattr(azure_functions_validation, name), (
                f"{name} should no longer be exported"
            )


# ---------------------------------------------------------------------------
# 2. Error Format Stability
# ---------------------------------------------------------------------------


class BodyModel(BaseModel):
    name: str = Field(min_length=1)
    age: int = Field(ge=0)


class RespModel(BaseModel):
    message: str


def _make_request(body: bytes) -> Mock:
    mock_req = Mock(spec=HttpRequest)
    mock_req.method = "POST"
    mock_req.url = "http://test"
    mock_req.get_body.return_value = body
    mock_req.params = {}
    mock_req.route_params = {}
    mock_req.headers = {}
    return mock_req


class TestErrorFormat:
    """Error envelope must always be {"detail": [...]}."""

    def test_validation_error_envelope(self) -> None:
        @validate_http(body=BodyModel)
        def handler(req: HttpRequest, body: BodyModel) -> dict[str, object]:
            return {"ok": True}

        resp = handler(_make_request(b'{"name": "", "age": -1}'))
        assert resp.status_code == 422
        data = json.loads(resp.get_body().decode())
        assert "detail" in data
        assert isinstance(data["detail"], list)
        assert len(data["detail"]) > 0
        first = data["detail"][0]
        assert "loc" in first
        assert "msg" in first
        assert "type" in first

    def test_json_parse_error_envelope(self) -> None:
        @validate_http(body=BodyModel)
        def handler(req: HttpRequest, body: BodyModel) -> dict[str, object]:
            return {"ok": True}

        resp = handler(_make_request(b"not-json"))
        assert resp.status_code == 400
        data = json.loads(resp.get_body().decode())
        assert "detail" in data

    def test_response_validation_error_envelope(self) -> None:
        @validate_http(body=BodyModel, response_model=RespModel)
        def handler(req: HttpRequest, body: BodyModel) -> dict[str, object]:
            return {"wrong_field": True}

        resp = handler(_make_request(b'{"name": "ok", "age": 1}'))
        assert resp.status_code == 500
        data = json.loads(resp.get_body().decode())
        assert "detail" in data
        assert data["detail"][0]["type"] == "response_validation_error"
        assert data["detail"][0]["loc"] == ["response"]


# ---------------------------------------------------------------------------
# 3. Error Path — custom formatter takes precedence
# ---------------------------------------------------------------------------


class TestErrorPath:
    """Per-handler error_formatter must override default formatting."""

    def test_custom_formatter_receives_exception_and_status(self) -> None:
        captured: list[tuple[Exception, int]] = []

        def fmt(exc: Exception, status: int) -> dict[str, object]:
            captured.append((exc, status))
            return {"custom": True}

        @validate_http(body=BodyModel, error_formatter=fmt)
        def handler(req: HttpRequest, body: BodyModel) -> dict[str, object]:
            return {"ok": True}

        resp = handler(_make_request(b'{"name": "", "age": -1}'))
        assert resp.status_code == 422
        data = json.loads(resp.get_body().decode())
        assert data["custom"] is True
        assert len(captured) == 1
        assert captured[0][1] == 422

    def test_custom_formatter_for_response_error(self) -> None:
        def fmt(exc: Exception, status: int) -> dict[str, object]:
            return {"response_error": True, "status": status}

        @validate_http(body=BodyModel, response_model=RespModel, error_formatter=fmt)
        def handler(req: HttpRequest, body: BodyModel) -> dict[str, object]:
            return {"no_message": True}

        resp = handler(_make_request(b'{"name": "ok", "age": 1}'))
        assert resp.status_code == 500
        data = json.loads(resp.get_body().decode())
        assert data["response_error"] is True
        assert data["status"] == 500


# ---------------------------------------------------------------------------
# 4. Response Validation
# ---------------------------------------------------------------------------


class TestResponseValidation:
    """Response model enforcement."""

    def test_valid_response_serializes(self) -> None:
        @validate_http(body=BodyModel, response_model=RespModel)
        def handler(req: HttpRequest, body: BodyModel) -> RespModel:
            return RespModel(message=f"hi {body.name}")

        resp = handler(_make_request(b'{"name": "Alice", "age": 30}'))
        assert resp.status_code == 200
        data = json.loads(resp.get_body().decode())
        assert data["message"] == "hi Alice"

    def test_http_response_bypass(self) -> None:
        @validate_http(body=BodyModel, response_model=RespModel)
        def handler(req: HttpRequest, body: BodyModel) -> HttpResponse:
            return HttpResponse(body="raw", status_code=201)

        resp = handler(_make_request(b'{"name": "Bob", "age": 25}'))
        assert resp.status_code == 201

    def test_no_response_model_passes_through(self) -> None:
        @validate_http(body=BodyModel)
        def handler(req: HttpRequest, body: BodyModel) -> dict[str, str]:
            return {"name": body.name}

        resp = handler(_make_request(b'{"name": "Carol", "age": 20}'))
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 5. Type Exports — importable without runtime error
# ---------------------------------------------------------------------------


class TestTypeExports:
    """Ensure types are importable and usable for annotations."""

    def test_error_formatter_annotation(self) -> None:
        def fmt(exc: Exception, code: int) -> dict[str, str]:
            return {"err": str(exc)}

        result = fmt(ValueError("test"), 422)
        assert result["err"] == "test"

    def test_response_validation_error_is_raisable(self) -> None:
        with pytest.raises(ResponseValidationError, match="boom"):
            raise ResponseValidationError("boom")

    def test_response_validation_error_str(self) -> None:
        err = ResponseValidationError("test message")
        assert str(err) == "test message"
