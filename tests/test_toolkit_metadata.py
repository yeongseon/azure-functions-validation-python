"""Tests for the _azure_functions_toolkit_metadata convention.

Mirrors test_toolkit_metadata.py in sibling packages (db, logging, langgraph)
to ensure consistent convention compliance across the ecosystem.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

from azure.functions import HttpRequest
from pydantic import BaseModel

from azure_functions_validation import validate_http

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TOOLKIT_META_ATTR = "_azure_functions_toolkit_metadata"


class UserModel(BaseModel):
    name: str
    age: int


class QueryModel(BaseModel):
    page: int = 1


def _make_request(body: bytes = b'{"name": "Alice", "age": 30}') -> Mock:
    mock_req = Mock(spec=HttpRequest)
    mock_req.method = "POST"
    mock_req.url = "http://test"
    mock_req.get_body.return_value = body
    mock_req.params = {}
    mock_req.route_params = {}
    mock_req.headers = {}
    return mock_req


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestToolkitMetadataConvention:
    """Verify _azure_functions_toolkit_metadata convention compliance."""

    def test_metadata_attribute_exists_on_decorated_function(self) -> None:
        @validate_http(body=UserModel)
        def handler(req: HttpRequest, body: UserModel) -> dict[str, object]:
            return {"ok": True}

        assert hasattr(handler, _TOOLKIT_META_ATTR)

    def test_metadata_is_dict_with_validation_namespace(self) -> None:
        @validate_http(body=UserModel)
        def handler(req: HttpRequest, body: UserModel) -> dict[str, object]:
            return {"ok": True}

        meta = getattr(handler, _TOOLKIT_META_ATTR)
        assert isinstance(meta, dict)
        assert "validation" in meta

    def test_metadata_payload_has_version(self) -> None:
        @validate_http(body=UserModel)
        def handler(req: HttpRequest, body: UserModel) -> dict[str, object]:
            return {"ok": True}

        meta = getattr(handler, _TOOLKIT_META_ATTR)
        payload = meta["validation"]
        assert payload["version"] == 1

    def test_metadata_payload_contains_models(self) -> None:
        @validate_http(body=UserModel, query=QueryModel, response_model=UserModel)
        def handler(
            req: HttpRequest, body: UserModel, query: QueryModel
        ) -> dict[str, object]:
            return {"ok": True}

        meta = getattr(handler, _TOOLKIT_META_ATTR)
        payload = meta["validation"]
        assert payload["body"] is UserModel
        assert payload["query"] is QueryModel
        assert payload["response_model"] is UserModel
        assert payload["path"] is None
        assert payload["headers"] is None

    def test_metadata_payload_none_when_no_models(self) -> None:
        @validate_http(response_model=UserModel)
        def handler(req: HttpRequest) -> dict[str, object]:
            return {"name": "Alice", "age": 30}

        meta = getattr(handler, _TOOLKIT_META_ATTR)
        payload = meta["validation"]
        assert payload["body"] is None
        assert payload["query"] is None
        assert payload["path"] is None
        assert payload["headers"] is None
        assert payload["response_model"] is UserModel

    def test_toolkit_attr_absent_on_plain_function(self) -> None:
        def handler(req: HttpRequest) -> dict[str, object]:
            return {"ok": True}

        assert not hasattr(handler, _TOOLKIT_META_ATTR)

    def test_namespace_preservation_with_foreign_metadata(self) -> None:
        """Other namespaces set before decoration must survive."""

        @validate_http(body=UserModel)
        def handler(req: HttpRequest, body: UserModel) -> dict[str, object]:
            return {"ok": True}

        # Simulate another package adding its own namespace
        meta: dict[str, Any] = getattr(handler, _TOOLKIT_META_ATTR)
        meta["other_package"] = {"version": 1, "foo": "bar"}
        setattr(handler, _TOOLKIT_META_ATTR, meta)

        # Verify both namespaces coexist
        updated = getattr(handler, _TOOLKIT_META_ATTR)
        assert "validation" in updated
        assert "other_package" in updated
        assert updated["validation"]["version"] == 1
        assert updated["other_package"]["foo"] == "bar"

    def test_async_handler_has_metadata(self) -> None:
        @validate_http(body=UserModel)
        async def handler(req: HttpRequest, body: UserModel) -> dict[str, object]:
            return {"ok": True}

        assert hasattr(handler, _TOOLKIT_META_ATTR)
        meta = getattr(handler, _TOOLKIT_META_ATTR)
        assert "validation" in meta
        assert meta["validation"]["body"] is UserModel

