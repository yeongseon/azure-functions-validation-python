"""Offline regression for the response field aliases recipe (#673)."""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import azure.functions as func
from pydantic import BaseModel, Field
import pytest

from azure_functions_validation import validate_http
from azure_functions_validation.testing import MockHttpRequest

_PATH = (
    Path(__file__).resolve().parents[1] / "examples" / "response_field_aliases" / "function_app.py"
)


def _load() -> ModuleType:
    spec = spec_from_file_location("response_field_aliases_example", _PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_response_serialization_uses_aliases() -> None:
    """Default: response_by_alias=True emits declared Field aliases
    and serialization_alias on the wire.
    """
    app = _load()
    response = app.get_item_summary(MockHttpRequest(method="GET"))

    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/json"
    assert response.get_body() == b'{"id":1,"title":"Widget","active":true}'
    assert json.loads(response.get_body()) == {"id": 1, "title": "Widget", "active": True}


def test_response_by_alias_false_uses_python_field_names() -> None:
    """Explicit response_by_alias=False emits Python field names
    instead of aliases or serialization_alias.
    """
    app = _load()
    response = app.get_item_summary_by_name(MockHttpRequest(method="GET"))

    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/json"
    assert response.get_body() == b'{"item_id":1,"title":"Widget","is_active":true}'
    assert json.loads(response.get_body()) == {
        "item_id": 1,
        "title": "Widget",
        "is_active": True,
    }


def test_serialization_only_alias_explicit_isolation() -> None:
    """Field(serialization_alias=...) affects output wire JSON but not model instantiation."""

    class SerializationOnlyResponse(BaseModel):
        display_name: str = Field(serialization_alias="displayName")

    @validate_http(response_model=SerializationOnlyResponse)
    def handler_aliased(req: func.HttpRequest) -> SerializationOnlyResponse:
        return SerializationOnlyResponse(display_name="Ada")

    @validate_http(response_model=SerializationOnlyResponse, response_by_alias=False)
    def handler_by_name(req: func.HttpRequest) -> SerializationOnlyResponse:
        return SerializationOnlyResponse(display_name="Ada")

    req = MockHttpRequest(method="GET")

    aliased_response = handler_aliased(req)
    assert aliased_response.status_code == 200
    assert aliased_response.headers["Content-Type"] == "application/json"
    assert aliased_response.get_body() == b'{"displayName":"Ada"}'
    assert json.loads(aliased_response.get_body()) == {"displayName": "Ada"}

    by_name_response = handler_by_name(req)
    assert by_name_response.status_code == 200
    assert by_name_response.headers["Content-Type"] == "application/json"
    assert by_name_response.get_body() == b'{"display_name":"Ada"}'
    assert json.loads(by_name_response.get_body()) == {"display_name": "Ada"}


def test_response_by_alias_without_response_model_raises_value_error() -> None:
    """response_by_alias=False requires response_model to be configured."""
    with pytest.raises(ValueError, match="response serialization options require response_model"):

        @validate_http(response_by_alias=False)
        def _invalid(req: func.HttpRequest) -> Any:
            return None


def test_docs_page_embeds_the_example_verbatim() -> None:
    doc = (_PATH.parents[2] / "docs" / "examples" / "response_field_aliases.md").read_text(
        encoding="utf-8"
    )
    assert f"```python\n{_PATH.read_text(encoding='utf-8')}```" in doc
