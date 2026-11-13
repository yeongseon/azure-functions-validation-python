"""Offline regression for the response status/header override recipe (#630)."""

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
from types import ModuleType

from azure_functions_validation.testing import MockHttpRequest

_PATH = Path(__file__).resolve().parents[1] / "examples" / "response_overrides" / "function_app.py"


def _load() -> ModuleType:
    spec = spec_from_file_location("response_overrides_example", _PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_create_item_overrides_status_and_adds_header() -> None:
    response = _load().create_item(MockHttpRequest(method="POST"))
    assert response.status_code == 201
    assert response.headers["Location"] == "/api/items/1"
    assert response.headers["Content-Type"] == "application/json"
    assert response.get_body() == b'{"id":1,"name":"alpha"}'


def test_response_model_still_filters_undeclared_fields() -> None:
    response = _load().create_item(MockHttpRequest(method="POST"))
    assert "internal_note" not in json.loads(response.get_body())


def test_omitted_status_inherits_decorator_status() -> None:
    response = _load().accept_item(MockHttpRequest(method="POST"))
    assert response.status_code == 202
    assert response.headers["X-Example"] == "accepted"
    assert json.loads(response.get_body()) == {"id": 2, "name": "beta"}


def test_override_does_not_bypass_response_validation() -> None:
    response = _load().broken_item(MockHttpRequest(method="POST"))
    assert response.status_code == 500
    assert json.loads(response.get_body())["detail"][0]["msg"] == "Internal Server Error"


def test_docs_page_embeds_the_example_verbatim() -> None:
    doc = (_PATH.parents[2] / "docs" / "examples" / "response_overrides.md").read_text(
        encoding="utf-8"
    )
    assert f"```python\n{_PATH.read_text(encoding='utf-8')}```" in doc
