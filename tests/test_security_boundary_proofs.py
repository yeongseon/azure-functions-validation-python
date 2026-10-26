import json

import azure.functions as func
from pydantic import BaseModel
import pytest

from azure_functions_validation import HttpError, validate_http
from azure_functions_validation.testing import MockHttpRequest


class Response(BaseModel):
    value: int


@pytest.mark.anyio
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("helper", [False, True])
@pytest.mark.parametrize("formatter_fails", [False, True])
async def test_default_5xx_and_failing_formatter_never_echo_input_or_credentials(
    asynchronous: bool, helper: bool, formatter_fails: bool
) -> None:
    secret = "CANARY-secret-credential-input"

    def formatter(exc: Exception, status: int) -> dict[str, str]:
        raise RuntimeError(secret)

    def handler(req: func.HttpRequest) -> dict[str, str]:
        return {"value": secret}

    async def async_handler(req: func.HttpRequest) -> dict[str, str]:
        return handler(req)

    wrapped = validate_http(
        response_model=Response, error_formatter=formatter if formatter_fails else None
    )(async_handler if asynchronous else handler)
    request_type = MockHttpRequest if helper else func.HttpRequest
    request = request_type(
        method="POST",
        url="https://example.test",
        body=secret.encode(),
        headers={"Authorization": secret},
    )
    response = await wrapped(request) if asynchronous else wrapped(request)
    assert response.status_code == 500
    assert secret not in response.get_body().decode()
    assert secret not in repr(dict(response.headers))


@pytest.mark.parametrize("auth", [func.AuthLevel.FUNCTION, func.AuthLevel.ADMIN])
def test_validation_preserves_host_owned_authentication(auth: func.AuthLevel) -> None:
    app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

    @app.route(route="protected", auth_level=auth)
    @validate_http()
    def handler(req: func.HttpRequest) -> None:
        raise HttpError(500, "private")

    bindings = json.loads(app.get_functions()[0].get_function_json())["bindings"]
    trigger = next(binding for binding in bindings if binding["type"] == "httpTrigger")
    assert trigger["authLevel"].casefold() == auth.value
