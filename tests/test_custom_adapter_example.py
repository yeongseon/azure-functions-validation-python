"""Conformance run for the minimal custom adapter example (#637).

``TestTinyAdapterConformance`` shows the success path: pytest collects every inherited
``test_*`` method of the shipped ``AdapterConformanceTests`` for the custom adapter. The
``Broken*`` suites are not collected (no ``Test`` prefix); the tests below run them on purpose
and assert that the suite catches each deliberate contract violation.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from azure_functions_validation import validate_http
from azure_functions_validation.testing import AdapterConformanceTests, MockHttpRequest
from examples.custom_adapter.adapter import Schema, TinyAdapter


class _TinyModels:
    def body_model(self) -> Schema:
        return Schema({"name": str, "count": int})

    def query_model(self) -> Schema:
        return Schema({"limit": int})

    def path_model(self) -> Schema:
        return Schema({"item_id": int})

    def headers_model(self) -> Schema:
        return Schema({"X-Request-Id": str})

    def response_model(self) -> Schema:
        return Schema({"status": str})


class TestTinyAdapterConformance(_TinyModels, AdapterConformanceTests):
    """Success case: the example adapter passes the whole shipped suite."""

    def make_adapter(self) -> TinyAdapter:
        return TinyAdapter()


class _Forwarding:
    """Delegates every adapter method to ``TinyAdapter``; subclasses override one behavior."""

    def __init__(self) -> None:
        self._inner = TinyAdapter()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class _LegacyAdapter(_Forwarding):
    """Like a pre-0.17 adapter: it has no ``serialize_response``."""

    def __getattr__(self, name: str) -> Any:
        if name == "serialize_response":
            raise AttributeError(name)
        return super().__getattr__(name)


class _UnprefixedLocAdapter(_Forwarding):
    """Violates the contract: query error ``loc`` lacks the leading ``query`` source."""

    def parse_query(self, req: Any, model: Schema) -> Any:
        try:
            return self._inner.parse_query(req, model)
        except Exception as exc:
            for entry in exc.errors:  # type: ignore[attr-defined]
                entry["loc"] = entry["loc"][1:]
            raise


class _WrongMalformedErrorAdapter(_Forwarding):
    """Violates the contract: malformed JSON raises ``ValueError`` instead of the taxonomy type."""

    def parse_body(self, req: Any, model: Schema) -> Any:
        if req.get_body() == b"{invalid":
            raise ValueError("invalid JSON")
        return self._inner.parse_body(req, model)


def _suite_for(adapter: Any) -> AdapterConformanceTests:
    class BrokenAdapterConformance(_TinyModels, AdapterConformanceTests):
        def make_adapter(self) -> Any:
            return adapter

    return BrokenAdapterConformance()


@pytest.mark.parametrize(
    ("adapter", "failing_test", "error"),
    [
        pytest.param(
            _LegacyAdapter(),
            "test_serialize_response_for_declared_model",
            AttributeError,
            id="missing-serialize_response",
        ),
        pytest.param(
            _UnprefixedLocAdapter(),
            "test_query_parsing_and_error_location",
            AssertionError,
            id="unprefixed-loc",
        ),
        pytest.param(
            _WrongMalformedErrorAdapter(),
            "test_invalid_json_raises_malformed_request_error",
            AssertionError,
            id="wrong-malformed-exception",
        ),
    ],
)
def test_conformance_suite_catches_contract_violations(
    adapter: Any, failing_test: str, error: type[Exception]
) -> None:
    with pytest.raises(error):
        getattr(_suite_for(adapter), failing_test)()


def test_the_legacy_adapter_only_fails_where_the_missing_method_matters() -> None:
    suite = _suite_for(_LegacyAdapter())
    suite.test_serialize_supported_values()
    suite.test_validate_response_accepts_valid_value()


def test_custom_adapter_drives_validate_http_end_to_end() -> None:
    @validate_http(
        body=Schema({"name": str, "count": int}),
        response_model=Schema({"name": str}),
        adapter=TinyAdapter(),
    )
    def handler(req: Any, body: dict[str, Any]) -> dict[str, Any]:
        return {"name": body["name"], "count": body["count"]}

    ok = handler(MockHttpRequest(method="POST", json={"name": "a", "count": "2"}))
    assert ok.status_code == 200
    # serialize_response keeps only the declared model's fields.
    assert json.loads(ok.get_body()) == {"name": "a"}

    bad = handler(MockHttpRequest(method="POST", json={"name": "a"}))
    assert bad.status_code == 422
    assert [(e["loc"], e["type"]) for e in json.loads(bad.get_body())["detail"]] == [
        (["body", "count"], "missing")
    ]


def test_docs_page_embeds_the_adapter_verbatim() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "examples" / "custom_adapter" / "adapter.py").read_text(encoding="utf-8")
    page = (root / "docs" / "examples" / "custom_adapter.md").read_text(encoding="utf-8")
    assert f"```python\n{source}```" in page
