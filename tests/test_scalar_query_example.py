"""Offline regression for the standalone scalar-query recipe (#631)."""

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
from types import ModuleType
from typing import Annotated, Any
from urllib.parse import parse_qsl

import azure.functions as func
from pydantic import BaseModel, Field
import pytest

from azure_functions_validation import validate_http
from azure_functions_validation.testing import MockHttpRequest

_PATH = Path(__file__).resolve().parents[1] / "examples" / "scalar_query" / "function_app.py"


def _load() -> ModuleType:
    spec = spec_from_file_location("scalar_query_example", _PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _get(handler_name: str, query: str) -> tuple[int, dict[str, Any]]:
    request = MockHttpRequest(
        url=f"http://localhost/api/scalar_query?{query}", params=dict(parse_qsl(query))
    )
    response = getattr(_load(), handler_name)(request)
    return response.status_code, json.loads(response.get_body())


def test_defaults_are_validated_and_injected() -> None:
    status, body = _get("search_items", "tags=a")
    assert status == 200
    assert body == {"page": 1, "tags": ["a"], "since": None, "color": "red", "size": 10}


def test_values_are_coerced_to_typed_python_values() -> None:
    query = "tags=a&tags=b&page=3&since=2026-01-02&color=blue&page-size=7&unknown=ignored"
    status, body = _get("search_items", query)
    assert status == 200
    assert body == {
        "page": 3,
        "tags": ["a", "b"],
        "since": "2026-01-02",
        "color": "blue",
        "size": 7,
    }


@pytest.mark.parametrize(
    ("query", "loc", "error_type"),
    [
        ("tags=a&page=0", ["query", "page"], "greater_than_equal"),
        ("tags=a&page=x", ["query", "page"], "int_parsing"),
        ("tags=a&color=green", ["query", "color"], "enum"),
        ("tags=a&page-size=99", ["query", "page-size"], "less_than_equal"),
        ("tags=a&page=1&page=2", ["query", "page"], "int_type"),
        ("", ["query", "tags"], "missing"),
    ],
)
def test_invalid_input_is_a_422_at_the_wire_name(
    query: str, loc: list[str], error_type: str
) -> None:
    status, body = _get("search_items", query)
    assert status == 422
    assert [(e["loc"], e["type"]) for e in body["detail"]] == [(loc, error_type)]


def test_feature_is_opt_in() -> None:
    status, body = _get("undeclared_query", "page=not-a-number")
    assert status == 200
    assert body == {"page": "not-a-number"}


def test_declaration_cannot_be_combined_with_query_model() -> None:
    class Model(BaseModel):
        page: int = 1

    with pytest.raises(ValueError):

        @validate_http(query=Model, query_params={"page": Annotated[int, Field(ge=1)]})
        def handler(req: func.HttpRequest, query: Model, *, page: int = 1) -> None:
            return None


def test_docs_page_embeds_the_example_verbatim() -> None:
    doc = (_PATH.parents[2] / "docs" / "examples" / "scalar_query.md").read_text(encoding="utf-8")
    assert f"```python\n{_PATH.read_text(encoding='utf-8')}```" in doc
