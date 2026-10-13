import asyncio
from collections.abc import Callable
import json
from typing import Any

from azure.functions import HttpRequest
from pydantic import BaseModel
import pytest

from azure_functions_validation import (
    validate_http,
)

RequestFactory = Callable[..., HttpRequest]


class BodyInput(BaseModel):
    body_value: int


class QueryInput(BaseModel):
    query_value: int


class PathInput(BaseModel):
    path_value: int


class HeaderInput(BaseModel):
    header_value: int


SOURCE_COMBINATIONS: list[tuple[dict[str, Any], list[str]]] = [
    ({"body": BodyInput}, ["body"]),
    ({"query": QueryInput, "path": PathInput}, ["query", "path"]),
    (
        {"body": BodyInput, "query": QueryInput, "path": PathInput},
        ["body", "query", "path"],
    ),
    (
        {
            "body": BodyInput,
            "query": QueryInput,
            "path": PathInput,
            "headers": HeaderInput,
        },
        ["body", "query", "path", "headers"],
    ),
]


def test_opt_in_collects_body_and_query_errors(mock_request_factory: RequestFactory) -> None:
    @validate_http(
        body=BodyInput,
        query=QueryInput,
        aggregate_validation_errors=True,
    )
    def handler(
        req: HttpRequest,
        body: BodyInput,
        query: QueryInput,
    ) -> dict[str, bool]:
        return {"called": True}

    request = mock_request_factory(body=b"{}")

    response = handler(request)

    assert response.status_code == 422
    assert json.loads(response.get_body()) == {
        "detail": [
            {"loc": ["body", "body_value"], "msg": "Field required", "type": "missing"},
            {"loc": ["query", "query_value"], "msg": "Field required", "type": "missing"},
        ],
        "error_format_version": 1,
    }


@pytest.mark.parametrize(
    ("options", "expected_sources"),
    SOURCE_COMBINATIONS,
)
def test_opt_in_collects_configured_source_combinations(
    mock_request_factory: RequestFactory,
    options: dict[str, Any],
    expected_sources: list[str],
) -> None:
    @validate_http(**options, aggregate_validation_errors=True)
    def handler(req: HttpRequest) -> dict[str, bool]:
        return {"called": True}

    response = handler(mock_request_factory(body=b"{}"))

    assert response.status_code == 422
    assert [error["loc"][0] for error in json.loads(response.get_body())["detail"]] == (
        expected_sources
    )


def test_default_still_returns_first_source_error(mock_request_factory: RequestFactory) -> None:
    @validate_http(body=BodyInput, query=QueryInput)
    def handler(req: HttpRequest) -> dict[str, bool]:
        return {"called": True}

    response = handler(mock_request_factory(body=b"{}"))

    assert response.status_code == 422
    assert [error["loc"][0] for error in json.loads(response.get_body())["detail"]] == ["body"]


def test_aggregation_never_calls_handler_when_input_fails(
    mock_request_factory: RequestFactory,
) -> None:
    calls = 0

    @validate_http(body=BodyInput, query=QueryInput, aggregate_validation_errors=True)
    def handler(req: HttpRequest) -> dict[str, bool]:
        nonlocal calls
        calls += 1
        return {"called": True}

    handler(mock_request_factory(body=b"{}"))

    assert calls == 0


def test_aggregation_calls_successful_async_handler_once(
    mock_request_factory: RequestFactory,
) -> None:
    calls = 0

    @validate_http(body=BodyInput, query=QueryInput, aggregate_validation_errors=True)
    async def handler(
        req: HttpRequest,
        body: BodyInput,
        query: QueryInput,
    ) -> dict[str, bool]:
        nonlocal calls
        calls += 1
        return {"called": True}

    response = asyncio.run(
        handler(
            mock_request_factory(
                body=b'{"body_value": 1}',
                params={"query_value": "2"},
            )
        )
    )

    assert response.status_code == 200
    assert calls == 1
