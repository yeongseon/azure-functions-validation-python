from collections.abc import Callable
import inspect
import json

import azure.functions as func
from pydantic import BaseModel
import pytest

from azure_functions_validation import validate_http
from azure_functions_validation._endpoint import set_endpoint_metadata
from azure_functions_validation.testing import MockHttpRequest


class Body(BaseModel):
    value: int


blueprint_factory: Callable[[], func.Blueprint] = func.Blueprint


@pytest.mark.parametrize("blueprint", [False, True])
@pytest.mark.parametrize("metadata", [False, True])
@pytest.mark.parametrize("auth", [func.AuthLevel.FUNCTION, func.AuthLevel.ADMIN])
def test_validation_preserves_host_auth_binding(
    blueprint: bool, metadata: bool, auth: func.AuthLevel
) -> None:
    # Given an explicitly authenticated route, including Blueprint and metadata paths.
    app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)
    routes = blueprint_factory() if blueprint else app

    @validate_http(body=Body)
    def handler(req: func.HttpRequest) -> None:
        return None

    if metadata:
        set_endpoint_metadata(handler, handler, {"version": 1, "parameters": []})
    routes.route(route="secure", auth_level=auth)(handler)
    if blueprint:
        app.register_functions(routes)

    # When SDK registration materializes; Then validation cannot downgrade the trigger.
    binding = json.loads(app.get_functions()[0].get_function_json())["bindings"][0]
    assert binding["authLevel"].casefold() == auth.value
    assert "auth_level" not in inspect.signature(validate_http).parameters


def test_invalid_decorator_order_fails_without_changing_auth() -> None:
    # Given validation above a host route, an unsupported and explicitly rejected order.
    app = func.FunctionApp()

    @app.route(route="secure", auth_level=func.AuthLevel.FUNCTION)
    def handler(req: func.HttpRequest) -> None:
        return None

    # When decoration is attempted; Then no replacement/downgrade is silently accepted.
    with pytest.raises(RuntimeError, match="FunctionBuilder"):
        validate_http(body=Body)(handler)
    binding = json.loads(app.get_functions()[0].get_function_json())["bindings"][0]
    assert binding["authLevel"].casefold() == "function"


@pytest.mark.parametrize("credentials", [False, True])
def test_validation_does_not_authenticate_or_echo_function_credentials(credentials: bool) -> None:
    # Given identical malformed requests with/without host-owned credentials.
    @validate_http(body=Body)
    def handler(req: func.HttpRequest) -> None:
        pytest.fail("malformed input reached handler")

    req = MockHttpRequest(
        body=b'{"value":"CANARY_SECRET_input"}',
        url="https://example.test/api/secure?code=CANARY_SECRET_key"
        if credentials
        else "https://example.test/api/secure",
        headers={"x-functions-key": "CANARY_SECRET_key"} if credentials else {},
        params={"code": "CANARY_SECRET_key"} if credentials else {},
    )
    # When invoked directly (no host); Then validation alone makes no auth decision.
    response = handler(req)
    assert response.status_code == 422
    assert "CANARY_SECRET" not in response.get_body().decode()
