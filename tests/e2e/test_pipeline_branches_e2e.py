from __future__ import annotations

import os
from typing import Any

import pytest
import requests

BASE_URL = os.environ.get("E2E_BASE_URL", "").rstrip("/")
SKIP_REASON = "E2E_BASE_URL not set — skipping real-Azure e2e tests"
pytestmark = pytest.mark.skipif(not BASE_URL, reason=SKIP_REASON)

SANITIZED_500 = {
    "detail": [{"loc": [], "msg": "Internal Server Error", "type": "server_error"}],
    "error_format_version": 1,
}


def _request(method: str, path: str, **kwargs: Any) -> requests.Response:
    return requests.request(method, f"{BASE_URL}{path}", timeout=30, **kwargs)


def _assert_error_source(response: requests.Response, source: str) -> None:
    assert response.status_code == 422
    payload = response.json()
    assert payload["error_format_version"] == 1
    assert all({"loc", "msg", "type"} <= detail.keys() for detail in payload["detail"])
    assert any(detail["loc"][0] == source for detail in payload["detail"])


def test_query_path_and_header_injection_returns_echo() -> None:
    response = _request(
        "GET",
        "/api/pipeline/parameters/7",
        params={"limit": "3"},
        headers={"x-trace-id": "trace-508"},
    )

    assert response.status_code == 200
    assert response.json() == {"item_id": 7, "limit": 3, "trace_id": "trace-508"}


@pytest.mark.parametrize(
    ("path", "params", "headers", "source"),
    [
        ("/api/pipeline/parameters/7", {"limit": "bad"}, {"x-trace-id": "trace"}, "query"),
        ("/api/pipeline/parameters/7", {}, {}, "headers"),
        ("/api/pipeline/parameters/bad", {}, {"x-trace-id": "trace"}, "path"),
    ],
)
def test_non_body_validation_error_has_source_prefix(
    path: str,
    params: dict[str, str],
    headers: dict[str, str],
    source: str,
) -> None:
    response = _request("GET", path, params=params, headers=headers)

    _assert_error_source(response, source)


def test_async_endpoint_returns_200() -> None:
    response = _request("POST", "/api/pipeline/async", json={"value": 8})

    assert response.status_code == 200
    assert response.json() == {"value": 16}


def test_async_endpoint_returns_422() -> None:
    response = _request("POST", "/api/pipeline/async", json={"value": 0})

    _assert_error_source(response, "body")


def test_malformed_json_returns_400_envelope() -> None:
    response = _request(
        "POST",
        "/api/items",
        data="{not-json",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error_format_version"] == 1
    assert payload["detail"] == [{"loc": ["body"], "msg": "Invalid JSON", "type": "value_error"}]


def test_response_validation_failure_is_sanitized() -> None:
    response = _request("GET", "/api/pipeline/invalid-response")

    assert response.status_code == 500
    assert response.json() == SANITIZED_500
    assert "ResponseValidationError" not in response.text
    assert "PipelineItem" not in response.text


def test_dataclass_response_is_serialized() -> None:
    response = _request("GET", "/api/pipeline/dataclass")

    assert response.status_code == 200
    assert response.json() == {"name": "dataclass", "count": 2}


def test_none_response_returns_204() -> None:
    response = _request("DELETE", "/api/pipeline/empty")

    assert response.status_code == 204
    assert response.content == b""


def test_list_response_model_is_serialized() -> None:
    response = _request("GET", "/api/pipeline/list")

    assert response.status_code == 200
    assert response.json() == [
        {"name": "first", "count": 1},
        {"name": "second", "count": 2},
    ]


def test_formatter_failure_uses_sanitized_fallback() -> None:
    response = _request("POST", "/api/pipeline/formatter-failure", json={})

    assert response.status_code == 500
    assert response.json() == SANITIZED_500


def test_created_endpoint_returns_201() -> None:
    response = _request("POST", "/api/pipeline/created", json={"name": "created"})

    assert response.status_code == 201
    assert response.json() == {"name": "created", "count": 1}


def test_http_error_returns_404_envelope() -> None:
    response = _request("GET", "/api/pipeline/missing")

    assert response.status_code == 404
    assert response.json() == {
        "detail": [{"loc": [], "msg": "Pipeline item not found", "type": "http_error"}],
        "error_format_version": 1,
    }


def test_context_binding_passes_through_worker() -> None:
    response = _request("GET", "/api/pipeline/context")

    assert response.status_code == 200
    assert response.json() == {"function_name": "pipeline_context"}
