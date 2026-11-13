"""Offline regression for the validation-error status and media-type recipe (#632)."""

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
from types import ModuleType
from typing import Any

from azure_functions_validation.testing import MockHttpRequest

_PATH = (
    Path(__file__).resolve().parents[1] / "examples" / "error_status_media_type" / "function_app.py"
)
_MISSING = [{"loc": ["body", "text"], "type": "missing"}]


def _load() -> ModuleType:
    spec = spec_from_file_location("error_status_media_type_example", _PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _post(handler: str, body: bytes) -> tuple[int, str, Any]:
    response = getattr(_load(), handler)(MockHttpRequest(method="POST", body=body))
    return response.status_code, response.headers["Content-Type"], json.loads(response.get_body())


def _stable(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"loc": e["loc"], "type": e["type"]} for e in errors]


def test_default_is_422_json_when_no_override_is_declared() -> None:
    status, media, body = _post("comment_default", b"{}")
    assert (status, media) == (422, "application/json")
    assert _stable(body["detail"]) == _MISSING
    assert body["error_format_version"] == 1


def test_valid_request_is_unaffected_by_overrides() -> None:
    for handler in ("comment_default", "comment_status_only", "comment_problem"):
        assert _post(handler, b'{"text": "hi"}') == (200, "application/json", {"text": "hi"})


def test_status_only_override_changes_status_and_keeps_default_body() -> None:
    status, media, body = _post("comment_status_only", b"{}")
    assert (status, media) == (400, "application/json")
    assert _stable(body["detail"]) == _MISSING


def test_status_and_media_type_override_with_formatter_body() -> None:
    status, media, body = _post("comment_problem", b"{}")
    assert (status, media) == (400, "application/problem+json")
    assert body["title"] == "Invalid request"
    assert body["status"] == 400
    assert _stable(body["errors"]) == _MISSING


def test_malformed_json_is_not_eligible_for_the_override() -> None:
    assert _post("comment_default", b"broken")[:2] == (400, "application/json")
    status, media, body = _post("comment_problem", b"broken")
    assert (status, media) == (400, "application/json")
    assert body == {"title": "Invalid request", "status": 400, "errors": []}


def test_docs_page_embeds_the_example_verbatim() -> None:
    page = _PATH.parents[2] / "docs" / "examples" / "error_status_media_type.md"
    assert f"```python\n{_PATH.read_text(encoding='utf-8')}```" in page.read_text(encoding="utf-8")
