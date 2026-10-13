from collections.abc import Callable
import json
from typing import Any

from azure.functions import HttpRequest
from pydantic import BaseModel

from azure_functions_validation import (
    AdapterValidationError,
    AggregatedValidationError,
    MalformedRequestError,
    PydanticAdapter,
    validate_http,
)

RequestFactory = Callable[..., HttpRequest]


class BodyInput(BaseModel):
    body_value: int


class QueryInput(BaseModel):
    query_value: int


class CustomAdapter(PydanticAdapter):
    def parse_body(self, req: HttpRequest, model: Any) -> Any:
        raise AdapterValidationError(
            "body failed",
            [{"loc": ["body", "custom"], "msg": "invalid", "type": "custom"}],
        )

    def parse_query(self, req: HttpRequest, model: type[BaseModel]) -> Any:
        raise AdapterValidationError(
            "query failed",
            [{"loc": ["query", "custom"], "msg": "invalid", "type": "custom"}],
        )


class MalformedAfterValidationAdapter(CustomAdapter):
    def parse_query(self, req: HttpRequest, model: type[BaseModel]) -> Any:
        raise MalformedRequestError("malformed query")


class UnexpectedAfterValidationAdapter(CustomAdapter):
    def parse_query(self, req: HttpRequest, model: type[BaseModel]) -> Any:
        raise RuntimeError("adapter secret")


def test_custom_adapter_errors_are_aggregated_through_protocol(
    mock_request_factory: RequestFactory,
) -> None:
    seen_exception: Exception | None = None

    def formatter(exception: Exception, status_code: int) -> dict[str, Any]:
        nonlocal seen_exception
        seen_exception = exception
        assert status_code == 422
        return (
            {"detail": exception.errors} if isinstance(exception, AggregatedValidationError) else {}
        )

    @validate_http(
        body=BodyInput,
        query=QueryInput,
        adapter=CustomAdapter(),
        error_formatter=formatter,
        aggregate_validation_errors=True,
    )
    def handler(req: HttpRequest) -> dict[str, bool]:
        return {"called": True}

    response = handler(mock_request_factory())

    assert response.status_code == 422
    assert isinstance(seen_exception, AggregatedValidationError)
    assert len(json.loads(response.get_body())["detail"]) == 2


def test_malformed_input_discards_collected_validation_errors(
    mock_request_factory: RequestFactory,
) -> None:
    @validate_http(
        body=BodyInput,
        query=QueryInput,
        adapter=MalformedAfterValidationAdapter(),
        aggregate_validation_errors=True,
    )
    def handler(req: HttpRequest) -> dict[str, bool]:
        return {"called": True}

    response = handler(mock_request_factory())

    assert response.status_code == 400
    assert json.loads(response.get_body())["detail"] == [
        {"loc": ["body"], "msg": "malformed query", "type": "value_error"}
    ]


def test_formatter_failure_returns_sanitized_500(mock_request_factory: RequestFactory) -> None:
    def formatter(exception: Exception, status_code: int) -> dict[str, Any]:
        raise RuntimeError("formatter secret")

    @validate_http(
        body=BodyInput,
        error_formatter=formatter,
        aggregate_validation_errors=True,
    )
    def handler(req: HttpRequest) -> dict[str, bool]:
        return {"called": True}

    response = handler(mock_request_factory(body=b"{}"))

    assert response.status_code == 500
    assert json.loads(response.get_body())["detail"] == [
        {"loc": [], "msg": "Internal Server Error", "type": "server_error"}
    ]


def test_unexpected_error_discards_collected_errors_and_returns_500(
    mock_request_factory: RequestFactory,
) -> None:
    @validate_http(
        body=BodyInput,
        query=QueryInput,
        adapter=UnexpectedAfterValidationAdapter(),
        aggregate_validation_errors=True,
    )
    def handler(req: HttpRequest) -> dict[str, bool]:
        return {"called": True}

    response = handler(mock_request_factory())

    assert response.status_code == 500
    assert json.loads(response.get_body())["detail"] == [
        {"loc": [], "msg": "Internal Server Error", "type": "server_error"}
    ]


def test_legacy_locations_remain_unprefixed(mock_request_factory: RequestFactory) -> None:
    @validate_http(
        body=BodyInput,
        query=QueryInput,
        legacy_loc=True,
        aggregate_validation_errors=True,
    )
    def handler(req: HttpRequest) -> dict[str, bool]:
        return {"called": True}

    response = handler(mock_request_factory(body=b"{}"))

    assert [error["loc"] for error in json.loads(response.get_body())["detail"]] == [
        ["body_value"],
        ["query_value"],
    ]
