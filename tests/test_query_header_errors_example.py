"""Offline regression recipe for query and header validation errors (#629)."""

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from azure_functions_validation.testing import MockHttpRequest

_PATH = Path(__file__).resolve().parents[1] / "examples" / "query_header_errors" / "function_app.py"


def _load() -> ModuleType:
    spec = spec_from_file_location("query_header_errors_example", _PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_VALID_HEADERS = {"x-api-version": "v1"}


def _call(params: dict[str, str], headers: dict[str, str]) -> tuple[int, dict[str, Any]]:
    response = _load().list_items(MockHttpRequest(params=params, headers=headers))
    return response.status_code, json.loads(response.get_body())


def test_valid_request_is_accepted() -> None:
    status, body = _call({"limit": "5"}, _VALID_HEADERS)
    assert status == 200
    assert body == {"limit": 5, "api_version": "v1"}


def test_query_default_applies_when_omitted() -> None:
    status, body = _call({}, _VALID_HEADERS)
    assert status == 200
    assert body["limit"] == 10


@pytest.mark.parametrize(
    ("params", "headers", "loc", "error_type"),
    [
        ({"limit": "abc"}, _VALID_HEADERS, ["query", "limit"], "int_parsing"),
        ({"limit": "0"}, _VALID_HEADERS, ["query", "limit"], "greater_than_equal"),
        ({"limit": "101"}, _VALID_HEADERS, ["query", "limit"], "less_than_equal"),
        ({}, {}, ["headers", "x-api-version"], "missing"),
        ({}, {"x-api-version": "1"}, ["headers", "x-api-version"], "string_pattern_mismatch"),
    ],
)
def test_invalid_input_returns_422_with_stable_fields(
    params: dict[str, str], headers: dict[str, str], loc: list[str], error_type: str
) -> None:
    status, body = _call(params, headers)
    assert status == 422
    assert body["error_format_version"] == 1
    assert len(body["detail"]) == 1
    error = body["detail"][0]
    assert error["loc"] == loc
    assert error["type"] == error_type
    assert isinstance(error["msg"], str) and error["msg"]
