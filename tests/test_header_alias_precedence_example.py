"""Offline regression for the header alias precedence recipe (#636)."""

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from azure_functions_validation.testing import MockHttpRequest

_PATH = (
    Path(__file__).resolve().parents[1] / "examples" / "header_alias_precedence" / "function_app.py"
)


def _load() -> ModuleType:
    spec = spec_from_file_location("header_alias_precedence_example", _PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _get(headers: dict[str, str]) -> tuple[int, Any]:
    response = _load().whoami(MockHttpRequest(headers=headers))
    return response.status_code, json.loads(response.get_body())


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        pytest.param({"x-api-key": "new"}, "new", id="preferred-only"),
        pytest.param({"x-legacy-api-key": "old"}, "old", id="fallback-only"),
        pytest.param(
            {"x-api-key": "new", "x-legacy-api-key": "old"}, "new", id="both-preferred-first"
        ),
        pytest.param(
            {"x-legacy-api-key": "old", "x-api-key": "new"}, "new", id="both-fallback-first"
        ),
        pytest.param({"X-API-KEY": "NEW", "X-Legacy-Api-Key": "old"}, "NEW", id="case-insensitive"),
    ],
)
def test_first_listed_alias_wins_regardless_of_request_header_order(
    headers: dict[str, str], expected: str
) -> None:
    assert _get(headers) == (200, {"api_key": expected})


def test_unrelated_headers_do_not_satisfy_the_field() -> None:
    status, payload = _get({"x-other": "1"})
    assert status == 422
    (error,) = payload["detail"]
    assert (error["loc"], error["type"]) == (["headers", "x-api-key"], "missing")


def test_missing_error_names_the_first_listed_alias() -> None:
    _, payload = _get({})
    assert payload["detail"][0]["loc"] == ["headers", "x-api-key"]


def test_docs_page_embeds_the_example_verbatim() -> None:
    page = _PATH.parents[2] / "docs" / "examples" / "header_alias_precedence.md"
    assert f"```python\n{_PATH.read_text(encoding='utf-8')}```" in page.read_text(encoding="utf-8")
