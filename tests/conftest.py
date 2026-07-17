"""Shared pytest fixtures for the azure-functions-validation test suite.

Fixtures declared here are auto-discovered by pytest and available to every
test module without re-declaration, matching the convention used by sibling
DX Toolkit repositories (langgraph, durable-graph, db).
"""

from __future__ import annotations

from typing import Callable, Dict, Optional
from unittest.mock import Mock

from azure.functions import HttpRequest
import pytest


@pytest.fixture
def mock_request_factory() -> Callable[..., HttpRequest]:
    """Return a factory that builds mock ``HttpRequest`` objects.

    The factory accepts the request attributes exercised by the pipeline
    (method, url, body, params, route_params, headers) and returns a
    ``Mock`` spec'd against ``HttpRequest`` so attribute access is validated.
    """

    def _create_request(
        method: str = "GET",
        url: str = "http://example.com",
        body: bytes = b"",
        params: Optional[Dict[str, str]] = None,
        route_params: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> HttpRequest:
        mock_req = Mock(spec=HttpRequest)
        mock_req.method = method
        mock_req.url = url
        mock_req.get_body.return_value = body
        mock_req.params = params or {}
        mock_req.route_params = route_params or {}
        mock_req.headers = headers or {}

        return mock_req

    return _create_request
