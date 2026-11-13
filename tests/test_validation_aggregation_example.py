"""Offline regression for the multi-source aggregation walkthrough (#633)."""

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from azure_functions_validation.testing import MockHttpRequest

_PATH = (
    Path(__file__).resolve().parents[1] / "examples" / "validation_aggregation" / "function_app.py"
)
_BODY_ERROR = (["body", "sku"], "string_too_short")
_QUERY_ERROR = (["query", "quantity"], "greater_than_equal")


def _load() -> ModuleType:
    spec = spec_from_file_location("validation_aggregation_example", _PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _post(handler: str, **request: Any) -> tuple[int, list[tuple[list[str], str]]]:
    response = getattr(_load(), handler)(MockHttpRequest(method="POST", **request))
    payload = json.loads(response.get_body())
    return response.status_code, [(e["loc"], e["type"]) for e in payload.get("detail", [])]


_BOTH_INVALID: dict[str, Any] = {"json": {"sku": "a"}, "params": {"quantity": "0"}}


def test_default_reports_only_the_first_failing_source() -> None:
    assert _post("order_fail_fast", **_BOTH_INVALID) == (422, [_BODY_ERROR])


def test_default_reports_the_query_error_once_the_body_is_valid() -> None:
    request = {"json": {"sku": "abc"}, "params": {"quantity": "0"}}
    assert _post("order_fail_fast", **request) == (422, [_QUERY_ERROR])


def test_opt_in_reports_every_source_in_body_then_query_order() -> None:
    assert _post("order_aggregated", **_BOTH_INVALID) == (422, [_BODY_ERROR, _QUERY_ERROR])


def test_opt_in_missing_inputs_keep_source_labels_and_order() -> None:
    assert _post("order_aggregated", json={}, params={}) == (
        422,
        [(["body", "sku"], "missing"), (["query", "quantity"], "missing")],
    )


@pytest.mark.parametrize("handler", ["order_fail_fast", "order_aggregated"])
def test_valid_request_reaches_the_handler(handler: str) -> None:
    response = getattr(_load(), handler)(
        MockHttpRequest(method="POST", json={"sku": "abc"}, params={"quantity": "2"})
    )
    assert response.status_code == 200
    assert json.loads(response.get_body()) == {"sku": "abc", "quantity": 2}


@pytest.mark.parametrize("handler", ["order_fail_fast", "order_aggregated"])
def test_malformed_json_is_an_immediate_400_in_both_modes(handler: str) -> None:
    status, errors = _post(handler, body="broken", params={"quantity": "0"})
    assert status == 400
    assert [loc for loc, _ in errors] == [["body"]]


def test_docs_page_embeds_the_example_verbatim() -> None:
    page = _PATH.parents[2] / "docs" / "examples" / "validation_aggregation.md"
    assert f"```python\n{_PATH.read_text(encoding='utf-8')}```" in page.read_text(encoding="utf-8")
