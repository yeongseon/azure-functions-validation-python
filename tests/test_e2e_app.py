from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import anyio
import azure.functions as func

from azure_functions_validation.testing import MockHttpRequest

SANITIZED_500 = {
    "detail": [{"loc": [], "msg": "Internal Server Error", "type": "server_error"}],
    "error_format_version": 1,
}


class E2EAppLoadError(RuntimeError):
    pass


def _load_e2e_app() -> Any:
    module_path = Path(__file__).resolve().parents[1] / "examples/e2e_app/function_app.py"
    spec = spec_from_file_location("validation_example_e2e_pipeline", module_path)
    if spec is None or spec.loader is None:
        raise E2EAppLoadError(f"Failed to load E2E app from {module_path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _payload(response: func.HttpResponse) -> Any:
    return json.loads(response.get_body())


def test_non_body_models_are_injected_together() -> None:
    module = _load_e2e_app()
    request = MockHttpRequest(
        url="http://localhost/api/pipeline/parameters/7?limit=3",
        params={"limit": "3"},
        route_params={"item_id": "7"},
        headers={"x-trace-id": "trace-508"},
    )

    response = module.pipeline_parameters(request)

    assert response.status_code == 200
    assert _payload(response) == {"item_id": 7, "limit": 3, "trace_id": "trace-508"}


def test_non_body_validation_errors_include_source_prefixes() -> None:
    module = _load_e2e_app()
    requests_and_sources = [
        (
            MockHttpRequest(
                params={"limit": "bad"},
                route_params={"item_id": "7"},
                headers={"x-trace-id": "trace"},
            ),
            "query",
        ),
        (MockHttpRequest(route_params={"item_id": "7"}), "headers"),
        (
            MockHttpRequest(route_params={"item_id": "bad"}, headers={"x-trace-id": "trace"}),
            "path",
        ),
    ]

    for request, source in requests_and_sources:
        response = module.pipeline_parameters(request)
        assert response.status_code == 422
        assert any(detail["loc"][0] == source for detail in _payload(response)["detail"])


def test_async_handler_success_and_validation_error() -> None:
    module = _load_e2e_app()

    success = anyio.run(module.pipeline_async, MockHttpRequest(method="POST", json={"value": 8}))
    invalid = anyio.run(module.pipeline_async, MockHttpRequest(method="POST", json={"value": 0}))

    assert success.status_code == 200
    assert _payload(success) == {"value": 16}
    assert invalid.status_code == 422
    assert _payload(invalid)["detail"][0]["loc"][0] == "body"


def test_malformed_json_returns_400_envelope() -> None:
    module = _load_e2e_app()

    response = module.create_item(MockHttpRequest(method="POST", body="{not-json"))

    assert response.status_code == 400
    assert _payload(response) == {
        "detail": [{"loc": ["body"], "msg": "Invalid JSON", "type": "value_error"}],
        "error_format_version": 1,
    }


def test_response_validation_failure_is_sanitized() -> None:
    module = _load_e2e_app()

    response = module.pipeline_invalid_response(MockHttpRequest())

    assert response.status_code == 500
    assert _payload(response) == SANITIZED_500
    assert b"PipelineItem" not in response.get_body()


def test_dataclass_none_and_list_serialization() -> None:
    module = _load_e2e_app()
    request = MockHttpRequest()

    dataclass_response = module.pipeline_dataclass(request)
    empty_response = module.pipeline_empty(request)
    list_response = module.pipeline_list(request)

    assert dataclass_response.status_code == 200
    assert _payload(dataclass_response) == {"name": "dataclass", "count": 2}
    assert empty_response.status_code == 204
    assert empty_response.get_body() == b""
    assert list_response.status_code == 200
    assert _payload(list_response) == [
        {"name": "first", "count": 1},
        {"name": "second", "count": 2},
    ]


def test_formatter_failure_returns_sanitized_500() -> None:
    module = _load_e2e_app()

    response = module.pipeline_formatter_failure(MockHttpRequest(method="POST", json={}))

    assert response.status_code == 500
    assert _payload(response) == SANITIZED_500


def test_status_code_and_http_error_contracts() -> None:
    module = _load_e2e_app()

    created = module.pipeline_created(MockHttpRequest(method="POST", json={"name": "created"}))
    missing = module.pipeline_missing(MockHttpRequest())

    assert created.status_code == 201
    assert _payload(created) == {"name": "created", "count": 1}
    assert missing.status_code == 404
    assert _payload(missing) == {
        "detail": [{"loc": [], "msg": "Pipeline item not found", "type": "http_error"}],
        "error_format_version": 1,
    }


def test_context_binding_is_preserved() -> None:
    module = _load_e2e_app()
    context = Mock(spec=func.Context)
    context.function_name = "pipeline_context"

    response = module.pipeline_context(MockHttpRequest(), context=context)

    assert response.status_code == 200
    assert _payload(response) == {"function_name": "pipeline_context"}
