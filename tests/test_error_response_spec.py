from dataclasses import FrozenInstanceError
import json
from typing import Any

from azure.functions import HttpRequest, HttpResponse
from pydantic import BaseModel
import pytest

from azure_functions_validation import HttpError, validate_http
from azure_functions_validation.responses import ErrorResponseSpec, ValidationErrorResponse


@pytest.mark.parametrize("value", [ErrorResponseSpec(content={}), ValidationErrorResponse()])
def test_values_are_frozen_and_slotted(value: ErrorResponseSpec | ValidationErrorResponse) -> None:
    with pytest.raises(FrozenInstanceError):
        setattr(value, "status_code", 400)
    assert not hasattr(value, "__dict__")


def test_constructors_only_store_values() -> None:
    assert ValidationErrorResponse(status_code=500).status_code == 500
    assert ErrorResponseSpec(content={}, media_type="invalid").media_type == "invalid"


class Input(BaseModel):
    value: int


class Problem(BaseModel):
    title: str


class PrivateProblem(Problem):
    secret: str


def request(body: bytes = b"{}") -> HttpRequest:
    return HttpRequest("POST", "http://localhost", headers={}, body=body)


@pytest.mark.parametrize(
    "fixed", [None, ValidationErrorResponse(status_code=400, media_type="APPLICATION/PROBLEM+JSON")]
)
def test_rich_override_and_original_status(fixed: ValidationErrorResponse | None) -> None:
    seen: list[int] = []

    def formatter(exc: Exception, status: int) -> ErrorResponseSpec:
        seen.append(status)
        return ErrorResponseSpec(
            content={"title": "invalid"},
            status_code=400,
            media_type="application/problem+json",
            headers={"X-Trace": "yes"},
        )

    @validate_http(body=Input, error_formatter=formatter, validation_error_response=fixed)
    def handler(req: HttpRequest) -> None:
        pytest.fail("handler must not run")

    response = handler(request())
    assert seen == [422]
    assert response.status_code == 400
    assert response.headers["Content-Type"] == "application/problem+json"
    assert response.headers["X-Trace"] == "yes"
    assert json.loads(response.get_body()) == {"title": "invalid"}


@pytest.mark.parametrize("fixed", [None, ValidationErrorResponse(status_code=409)])
def test_omitted_transport_inherits(fixed: ValidationErrorResponse | None) -> None:
    @validate_http(
        body=Input,
        validation_error_response=fixed,
        error_formatter=lambda exc, status: ErrorResponseSpec(content={"ok": False}),
    )
    def handler(req: HttpRequest) -> None:
        pass

    response = handler(request())
    assert response.status_code == (409 if fixed else 422)
    assert response.headers["Content-Type"] == "application/json"


def test_status_only_reuses_default_body() -> None:
    @validate_http(body=Input, validation_error_response=ValidationErrorResponse(status_code=400))
    def handler(req: HttpRequest) -> None:
        pass

    response = handler(request())
    assert response.status_code == 400
    assert json.loads(response.get_body())["error_format_version"] == 1
    assert json.loads(response.get_body())["detail"][0]["loc"] == ["body", "value"]


def test_error_model_filters_nested_subclass_fields() -> None:
    class Envelope(BaseModel):
        problem: Problem

    @validate_http(
        body=Input,
        validation_error_response=ValidationErrorResponse(response_model=Envelope),
        error_formatter=lambda exc, status: {
            "problem": PrivateProblem(title="bad", secret="hidden")
        },
    )
    def handler(req: HttpRequest) -> None:
        pass

    assert json.loads(handler(request()).get_body()) == {"problem": {"title": "bad"}}


@pytest.mark.parametrize(
    "spec",
    [
        ErrorResponseSpec(content={}, status_code=409),
        ErrorResponseSpec(content={}, media_type="application/problem+json"),
        ErrorResponseSpec(content={}, status_code=True),
        ErrorResponseSpec(content={}, status_code=500),
        ErrorResponseSpec(content={}, media_type="text/plain"),
        ErrorResponseSpec(content={"secret": float("nan")}),
        ErrorResponseSpec(content={"secret": object()}),
        ErrorResponseSpec(content={}, headers={"Content-Length": "0"}),
    ],
)
def test_invalid_rich_result_fails_closed(spec: ErrorResponseSpec) -> None:
    @validate_http(
        body=Input,
        validation_error_response=ValidationErrorResponse(),
        error_formatter=lambda exc, status: spec,
    )
    def handler(req: HttpRequest) -> None:
        pass

    response = handler(request())
    assert response.status_code == 500
    assert json.loads(response.get_body()) == {
        "detail": [{"loc": [], "msg": "Internal Server Error", "type": "server_error"}],
        "error_format_version": 1,
    }
    assert response.headers["Content-Type"] == "application/json"


@pytest.mark.parametrize("result", [[], "secret", None, HttpResponse("secret"), {"title": 7}])
def test_invalid_formatter_or_model_content(result: Any) -> None:
    @validate_http(
        body=Input,
        validation_error_response=ValidationErrorResponse(response_model=Problem),
        error_formatter=lambda exc, status: result,
    )
    def handler(req: HttpRequest) -> None:
        pass

    assert handler(request()).status_code == 500


@pytest.mark.parametrize(
    "body,options,status",
    [
        (b"broken", {}, 400),
        (b"{}", {"max_body_bytes": 1}, 413),
        (b"{}", {"require_json_content_type": True}, 415),
    ],
)
def test_non_schema_failures_keep_classification(
    body: bytes, options: dict[str, Any], status: int
) -> None:
    @validate_http(
        body=Input,
        validation_error_response=ValidationErrorResponse(status_code=409),
        error_formatter=lambda exc, code: {"status": code},
        **options,
    )
    def handler(req: HttpRequest) -> None:
        pass

    response = handler(request(body))
    assert response.status_code == status
    assert json.loads(response.get_body()) == {"status": status}


@pytest.mark.parametrize("kind", ["malformed", "http422", "response", "binding", "serialization"])
@pytest.mark.parametrize("expose", [False, True])
def test_rich_result_rejected_outside_request_validation(kind: str, expose: bool) -> None:
    @validate_http(
        body=Input,
        response_model=Problem if kind == "response" else None,
        expose_internal_errors=expose,
        error_formatter=lambda exc, status: ErrorResponseSpec(
            content={"secret": str(exc)}, status_code=400
        ),
    )
    def handler(req: HttpRequest) -> Any:
        if kind == "http422":
            raise HttpError(422, "secret")
        return object() if kind == "serialization" else {}

    response = handler(
        None if kind == "binding" else request(b"broken" if kind == "malformed" else b'{"value":1}')
    )
    assert response.status_code == 500
    assert b"secret" not in response.get_body()


@pytest.mark.parametrize(
    "fixed",
    [
        ValidationErrorResponse(status_code=True),
        ValidationErrorResponse(status_code=500),
        ValidationErrorResponse(media_type="text/plain"),
        ValidationErrorResponse(media_type="application/problem+json"),
        ValidationErrorResponse(response_model=Problem),
    ],
)
def test_invalid_declaration_rejected(fixed: ValidationErrorResponse) -> None:
    with pytest.raises(ValueError):
        validate_http(validation_error_response=fixed)


def test_async_handler_has_same_error_contract() -> None:
    import anyio

    @validate_http(body=Input, validation_error_response=ValidationErrorResponse(status_code=400))
    async def handler(req: HttpRequest) -> None:
        pytest.fail("handler must not run")

    assert anyio.run(handler, request()).status_code == 400
