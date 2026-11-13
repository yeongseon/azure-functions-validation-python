"""Offline regression for the opt-in body-policy recipe (#635)."""

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from azure_functions_validation.testing import MockHttpRequest

_PATH = Path(__file__).resolve().parents[1] / "examples" / "body_policies" / "function_app.py"
_LIMIT = 64


def _load() -> ModuleType:
    spec = spec_from_file_location("body_policies_example", _PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _post(handler: str, body: bytes, content_type: str | None) -> tuple[int, dict[str, Any]]:
    headers = {} if content_type is None else {"Content-Type": content_type}
    response = getattr(_load(), handler)(MockHttpRequest(method="POST", body=body, headers=headers))
    return response.status_code, json.loads(response.get_body())


def _error(payload: dict[str, Any]) -> tuple[list[str], str]:
    (error,) = payload["detail"]
    return error["loc"], error["type"]


_OK = b'{"text": "hello"}'


def test_permitted_request_passes_the_strict_policies() -> None:
    assert _post("note_strict", _OK, "application/json") == (200, {"text": "hello"})
    assert _post("note_strict", _OK, "application/vnd.api+json; charset=utf-8")[0] == 200


@pytest.mark.parametrize("content_type", ["text/plain", None])
def test_wrong_or_missing_content_type_is_refused_with_415(content_type: str | None) -> None:
    status, payload = _post("note_strict", _OK, content_type)
    assert status == 415
    assert _error(payload) == (["headers", "content-type"], "unsupported_media_type")


def test_oversized_body_is_refused_with_413() -> None:
    body = json.dumps({"text": "x" * _LIMIT}).encode()
    assert len(body) > _LIMIT
    status, payload = _post("note_strict", body, "application/json")
    assert status == 413
    assert _error(payload) == (["body"], "payload_too_large")


def test_body_one_byte_over_the_limit_is_refused() -> None:
    text = "x" * (_LIMIT + 1 - len(b'{"text": ""}'))
    body = json.dumps({"text": text}).encode()
    assert len(body) == _LIMIT + 1
    assert _post("note_strict", body, "application/json")[0] == 413


def test_body_exactly_at_the_limit_is_permitted() -> None:
    text = "x" * (_LIMIT - len(b'{"text": ""}'))
    body = json.dumps({"text": text}).encode()
    assert len(body) == _LIMIT
    assert _post("note_strict", body, "application/json")[0] == 200


def test_policies_are_opt_in_the_default_handler_accepts_both() -> None:
    assert _post("note_relaxed", _OK, "text/plain") == (200, {"text": "hello"})
    big = json.dumps({"text": "x" * 10_000}).encode()
    assert _post("note_relaxed", big, None)[0] == 200


def test_docs_page_embeds_the_example_verbatim() -> None:
    page = _PATH.parents[2] / "docs" / "examples" / "body_policies.md"
    assert f"```python\n{_PATH.read_text(encoding='utf-8')}```" in page.read_text(encoding="utf-8")
