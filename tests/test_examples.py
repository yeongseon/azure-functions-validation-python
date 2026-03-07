from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
from typing import Any

import azure.functions as func


def _load_example_module(example_name: str) -> Any:
    module_path = (
        Path(__file__).resolve().parents[1] / "examples" / example_name / "function_app.py"
    )
    spec = spec_from_file_location(f"validation_example_{example_name}", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load example module from {module_path}")

    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_hello_validation_example_returns_validated_response() -> None:
    function_app = _load_example_module("hello_validation")
    request = func.HttpRequest(
        method="POST",
        url="/api/hello_validation",
        body=json.dumps({"name": "Azure"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    response = function_app.hello_validation(request)

    assert response.status_code == 200
    assert json.loads(response.get_body()) == {"message": "Hello Azure"}


def test_hello_validation_example_returns_validation_error() -> None:
    function_app = _load_example_module("hello_validation")
    request = func.HttpRequest(
        method="POST",
        url="/api/hello_validation",
        body=json.dumps({}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    response = function_app.hello_validation(request)

    assert response.status_code == 422
    payload = json.loads(response.get_body())
    assert "detail" in payload


def test_raw_http_response_example_returns_json() -> None:
    function_app = _load_example_module("hello_validation")
    request = func.HttpRequest(
        method="GET",
        url="/api/raw_http_response",
        body=b"",
        headers={},
    )

    response = function_app.raw_http_response(request)

    assert response.status_code == 200
    assert json.loads(response.get_body()) == {"message": "ok"}


def test_profile_validation_example_returns_typed_response() -> None:
    function_app = _load_example_module("profile_validation")
    request = func.HttpRequest(
        method="GET",
        url="/api/users/7?verbose=true",
        body=b"",
        params={"verbose": "true"},
        headers={"x-request-id": "req-123"},
        route_params={"user_id": "7"},
    )

    response = function_app.get_profile(request)

    assert response.status_code == 200
    assert json.loads(response.get_body()) == {
        "user_id": 7,
        "view": "detailed",
        "request_id": "req-123",
    }


def test_profile_validation_example_returns_header_validation_error() -> None:
    function_app = _load_example_module("profile_validation")
    request = func.HttpRequest(
        method="GET",
        url="/api/users/7",
        body=b"",
        params={},
        headers={},
        route_params={"user_id": "7"},
    )

    response = function_app.get_profile(request)

    assert response.status_code == 422
    payload = json.loads(response.get_body())
    assert "detail" in payload
