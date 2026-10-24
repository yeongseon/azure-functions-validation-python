"""Offline security proofs through the installed SDK and public HTTP entry point."""

import json
import logging
from unittest.mock import Mock

from azure.functions import HttpRequest, HttpResponse
from pydantic import BaseModel
import pytest

from azure_functions_validation import HttpError, PydanticAdapter, validate_http
from azure_functions_validation.errors import InternalServerError
from azure_functions_validation.testing import MockHttpRequest

SECRETS = (
    "CANARY_SECRET_exception",
    "DefaultEndpointsProtocol=https;AccountKey=CANARY_SECRET_connection",
    "Bearer CANARY_SECRET_token",
    "CANARY_SECRET_body",
    "CANARY_SECRET_pydantic_input",
)


class Output(BaseModel):
    value: int


class NativeOutput:
    """Non-Pydantic marker understood only by a custom backend."""


def request(helper: bool) -> HttpRequest:
    payload = json.dumps({"value": SECRETS[3]}).encode()
    if helper:
        return MockHttpRequest(body=payload)
    return HttpRequest("POST", "https://example.test", body=payload)


def assert_safe(response: HttpResponse, caplog: pytest.LogCaptureFixture) -> None:
    # Server-side logs intentionally keep exception details (exc_info) for operators
    # (#250); the trust boundary under test is what the HTTP *response* discloses.
    del caplog
    observed = response.get_body().decode() + repr(dict(response.headers))
    assert all(secret not in observed for secret in SECRETS)
    assert "Traceback (most recent call last)" not in observed
    assert "RuntimeError" not in observed
    assert "ValidationError" not in observed
    assert response.status_code >= 500


@pytest.mark.anyio
@pytest.mark.parametrize("helper", [False, True], ids=["sdk", "testing-helper"])
@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
@pytest.mark.parametrize(
    "failure",
    [
        "http-error",
        "response",
        "parse_body",
        "parse_query",
        "parse_path",
        "parse_headers",
        "serialize",
        "serialize_response",
        "format_error",
        "native-backend",
    ],
)
async def test_5xx_boundaries_never_echo_secrets_in_the_response(
    caplog: pytest.LogCaptureFixture, helper: bool, asynchronous: bool, failure: str
) -> None:
    # Given real SDK requests and a secret-bearing fault at each extension seam.
    adapter = PydanticAdapter()
    model = NativeOutput if failure == "native-backend" else Output
    if failure.startswith("parse_") or failure in {
        "serialize",
        "serialize_response",
        "format_error",
    }:
        setattr(adapter, failure, Mock(side_effect=RuntimeError(*SECRETS)))
    if failure == "native-backend":
        setattr(adapter, "validate_response", Mock(side_effect=RuntimeError(*SECRETS)))

    def handler(req: HttpRequest) -> dict[str, str]:
        if failure == "http-error":
            raise HttpError(503, list(SECRETS))
        return {"value": SECRETS[4]}

    async def async_handler(req: HttpRequest) -> dict[str, str]:
        return handler(req)

    wrapped = validate_http(
        adapter=adapter,
        response_model=model
        if failure in {"response", "serialize_response", "native-backend"}
        else None,
        body=Output if failure in {"parse_body", "format_error"} else None,
        query=Output if failure == "parse_query" else None,
        path=Output if failure == "parse_path" else None,
        headers=Output if failure == "parse_headers" else None,
    )(async_handler if asynchronous else handler)
    # serialize_response must be reached after successful response validation.
    if failure == "serialize_response":
        setattr(adapter, "validate_response", Mock(return_value=Output(value=1)))
    # When the public decorator is invoked; Then the transport never echoes secrets.
    with caplog.at_level(logging.DEBUG):
        response = await wrapped(request(helper)) if asynchronous else wrapped(request(helper))
    assert_safe(response, caplog)


@pytest.mark.anyio
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("expose", [False, True])
@pytest.mark.parametrize("formatter_mode", ["raises", "unserializable"])
async def test_failed_formatter_is_safe_even_with_debug_opt_in(
    caplog: pytest.LogCaptureFixture, asynchronous: bool, expose: bool, formatter_mode: str
) -> None:
    # Given a formatter that fails after receiving an original or sanitized exception.
    def formatter(exc: Exception, status: int) -> dict[str, str | set[str]]:
        if formatter_mode == "raises":
            raise RuntimeError(*SECRETS)
        return {"value": set(SECRETS)}

    def handler(req: HttpRequest) -> None:
        raise HttpError(500, list(SECRETS))

    async def async_handler(req: HttpRequest) -> None:
        handler(req)

    wrapped = validate_http(error_formatter=formatter, expose_internal_errors=expose)(
        async_handler if asynchronous else handler
    )
    # When invoked; Then even formatter exceptions/serialization cannot leak.
    with caplog.at_level(logging.DEBUG):
        response = await wrapped(request(True)) if asynchronous else wrapped(request(True))
    assert_safe(response, caplog)


@pytest.mark.parametrize("expose", [False, True])
def test_debug_opt_in_controls_only_formatter_access(expose: bool) -> None:
    # Given an explicitly redacting formatter, including with the unsafe opt-in.
    captured: list[Exception] = []

    def formatter(exc: Exception, status: int) -> dict[str, str]:
        captured.append(exc)
        return {"error": "redacted"}

    original = HttpError(500, SECRETS[0])

    @validate_http(error_formatter=formatter, expose_internal_errors=expose)
    def handler(req: HttpRequest) -> None:
        raise original

    # When invoked; Then opt-in never changes the fallback or performs automatic redaction.
    response = handler(request(True))
    assert json.loads(response.get_body()) == {"error": "redacted"}
    assert (captured[0] is original) == expose
    assert expose or isinstance(captured[0], InternalServerError)


def test_internal_error_exposure_defaults_off() -> None:
    # Given no debugging option; When a formatter sees a 5xx; Then it sees no original.
    def formatter(exc: Exception, status: int) -> dict[str, str]:
        return {"error": str(exc)}

    @validate_http(error_formatter=formatter)
    def handler(req: HttpRequest) -> None:
        raise HttpError(500, SECRETS[0])

    assert json.loads(handler(request(True)).get_body()) == {"error": "Internal Server Error"}
