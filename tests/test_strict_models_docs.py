import json
from pathlib import Path
import re
from typing import Any

from azure_functions_validation.testing import MockHttpRequest

_GUIDE = Path(__file__).resolve().parents[1] / "docs" / "strict-models.md"


def _python_block_after(heading: str) -> str:
    text = _GUIDE.read_text(encoding="utf-8")
    match = re.search(
        rf"^## {re.escape(heading)}\s*$.*?```python\n(.*?)```",
        text,
        re.DOTALL | re.MULTILINE,
    )
    if match is None:
        raise AssertionError(f"No Python block found after {heading!r}")
    return match.group(1)


def _load_snippet(heading: str) -> dict[str, Any]:
    namespace: dict[str, Any] = {}
    exec(_python_block_after(heading), namespace)
    return namespace


def test_strict_body_guide_snippet_reports_documented_errors() -> None:
    namespace = _load_snippet("Strict JSON body model")

    coercion_response = namespace["create_strict"](
        MockHttpRequest(method="POST", json={"count": "123", "enabled": "true"})
    )
    extra_response = namespace["create_strict"](
        MockHttpRequest(method="POST", json={"count": 123, "enabled": True, "role": "admin"})
    )

    assert coercion_response.status_code == 422
    assert json.loads(coercion_response.get_body()) == {
        "detail": [
            {
                "loc": ["body", "count"],
                "msg": "Input should be a valid integer",
                "type": "int_type",
            },
            {
                "loc": ["body", "enabled"],
                "msg": "Input should be a valid boolean",
                "type": "bool_type",
            },
        ],
        "error_format_version": 1,
    }
    assert json.loads(extra_response.get_body()) == {
        "detail": [
            {
                "loc": ["body", "role"],
                "msg": "Extra inputs are not permitted",
                "type": "extra_forbidden",
            }
        ],
        "error_format_version": 1,
    }


def test_lax_query_guide_snippet_accepts_url_strings() -> None:
    namespace = _load_snippet("Query, path, and header models")

    lax_response = namespace["list_lax"](MockHttpRequest(params={"limit": "10"}))
    strict_response = namespace["list_strict"](MockHttpRequest(params={"limit": "10"}))

    assert lax_response.status_code == 200
    assert json.loads(lax_response.get_body()) == {"limit": 10}
    assert strict_response.status_code == 422
    assert json.loads(strict_response.get_body()) == {
        "detail": [
            {
                "loc": ["query", "limit"],
                "msg": "Input should be a valid integer",
                "type": "int_type",
            }
        ],
        "error_format_version": 1,
    }
