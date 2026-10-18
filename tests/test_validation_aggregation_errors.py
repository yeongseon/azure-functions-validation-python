from collections.abc import Callable
import json
from typing import Any

from azure.functions import HttpRequest
from pydantic import BaseModel

from azure_functions_validation import (
    AdapterValidationError,
    AggregatedValidationError,
    MalformedRequestError,
    ValidationAdapter,
    validate_http,
)

RequestFactory = Callable[..., HttpRequest]


class BodyInput(BaseModel):
    body_value: int


class QueryInput(BaseModel):
    query_value: int


class CustomAdapter(ValidationAdapter):
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

    def parse_path(self, req: HttpRequest, model: type[BaseModel]) -> Any:
        return model.model_validate(req.route_params)

    def parse_headers(self, req: HttpRequest, model: type[BaseModel]) -> Any:
        return model.model_validate(dict(req.headers))

    def validate_response(self, obj: Any, model: Any, *, type_adapter: Any = None) -> Any:
        return obj

    def serialize(self, obj: Any) -> tuple[str | bytes, str]:
        return json.dumps(obj), "application/json"

    def serialize_response(
        self,
        obj: Any,
        model: Any,
        *,
        type_adapter: Any = None,
        by_alias: bool = True,
        exclude_none: bool = False,
        exclude_unset: bool = False,
    ) -> tuple[str | bytes, str]:
        return self.serialize(obj)

    def format_error(self, exc: Exception) -> dict[str, Any]:
        if isinstance(exc, AdapterValidationError):
            return {"detail": exc.errors}
        return {
            "detail": [
                {
                    "loc": ["body"] if isinstance(exc, MalformedRequestError) else [],
                    "msg": str(exc),
                    "type": "value_error",
                }
            ]
        }


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


class EmptyErrorAdapter(CustomAdapter):
    def parse_body(self, req: HttpRequest, model: Any) -> Any:
        raise AdapterValidationError("body failed", [])


def test_empty_adapter_error_list_still_blocks_handler(
    mock_request_factory: RequestFactory,
) -> None:
    calls = 0

    @validate_http(
        body=BodyInput,
        adapter=EmptyErrorAdapter(),
        aggregate_validation_errors=True,
    )
    def handler(req: HttpRequest) -> dict[str, bool]:
        nonlocal calls
        calls += 1
        return {"called": True}

    response = handler(mock_request_factory())

    assert response.status_code == 422
    assert json.loads(response.get_body())["detail"] == []
    assert calls == 0


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
