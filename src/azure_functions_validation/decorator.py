"""The main `validate_http` decorator."""

import asyncio
from functools import wraps
import inspect
from typing import Any, Callable, Coroutine, Optional, Type, TypeVar

from azure.functions import HttpRequest, HttpResponse
from pydantic import BaseModel, ValidationError

from .adapter import PydanticAdapter
from .exceptions import ResponseValidationError

F = TypeVar("F", bound=Callable[..., Any])


def validate_http(
    body: Optional[Type[BaseModel]] = None,
    query: Optional[Type[BaseModel]] = None,
    path: Optional[Type[BaseModel]] = None,
    headers: Optional[Type[BaseModel]] = None,
    request_model: Optional[Type[BaseModel]] = None,
    response_model: Optional[Type[Any]] = None,
) -> Callable[
    [F],
    Callable[[HttpRequest], Coroutine[Any, Any, HttpResponse] | HttpResponse],
]:
    """
    A decorator to validate Azure Functions HTTP requests and responses.
    """
    if request_model:
        body = request_model

    adapter = PydanticAdapter()

    def decorator(
        func: F,
    ) -> Callable[[HttpRequest], Coroutine[Any, Any, HttpResponse] | HttpResponse]:
        func_sig = inspect.signature(func)

        @wraps(func)
        def wrapper(req: HttpRequest) -> HttpResponse | Coroutine[Any, Any, HttpResponse]:
            validated_sources = {}
            # Perform validation for each source
            try:
                if body:
                    validated_sources["body"] = adapter.parse_body(req, body)
            except ValidationError as e:
                return HttpResponse(
                    adapter.serialize(adapter.format_error(e, ("body",)))[0],
                    status_code=422,
                    mimetype="application/json",
                )
            except ValueError as e:  # From json.loads
                return HttpResponse(
                    adapter.serialize(adapter.format_error(e, ("body",)))[0],
                    status_code=400,
                    mimetype="application/json",
                )

            try:
                if query:
                    validated_sources["query"] = adapter.parse_query(req, query)
            except ValidationError as e:
                return HttpResponse(
                    adapter.serialize(adapter.format_error(e, ("query",)))[0],
                    status_code=422,
                    mimetype="application/json",
                )

            try:
                if path:
                    validated_sources["path"] = adapter.parse_path(req, path)
            except ValidationError as e:
                return HttpResponse(
                    adapter.serialize(adapter.format_error(e, ("path",)))[0],
                    status_code=422,
                    mimetype="application/json",
                )

            try:
                if headers:
                    validated_sources["headers"] = adapter.parse_headers(req, headers)
            except ValidationError as e:
                return HttpResponse(
                    adapter.serialize(adapter.format_error(e, ("headers",)))[0],
                    status_code=422,
                    mimetype="application/json",
                )

            # Map validated sources to the handler's arguments
            handler_args = {}
            for param_name, param in func_sig.parameters.items():
                if param_name in validated_sources:
                    handler_args[param_name] = validated_sources[param_name]
                elif param.annotation is HttpRequest:
                    handler_args[param_name] = req

            # Call the actual handler
            if asyncio.iscoroutinefunction(func):

                async def async_runner() -> HttpResponse:
                    result = await func(**handler_args)
                    return _process_response(result, response_model, adapter)

                return async_runner()
            else:
                result = func(**handler_args)
                return _process_response(result, response_model, adapter)

        return wrapper

    return decorator


def _process_response(
    result: Any, response_model: Optional[Type[Any]], adapter: PydanticAdapter
) -> HttpResponse:
    """Shared logic to process the handler's response."""
    if isinstance(result, HttpResponse):
        return result

    try:
        if response_model:
            result = adapter.validate_response(result, response_model)

        content, content_type = adapter.serialize(result)
        return HttpResponse(content, status_code=200, mimetype=content_type)

    except ResponseValidationError as e:
        error_resp = adapter.format_error(e, ("response",))
        return HttpResponse(
            adapter.serialize(error_resp)[0],
            status_code=500,
            mimetype="application/json",
        )