"""Core decorator for HTTP request/response validation."""

import inspect
import json
from typing import Any, Callable, Optional

from azure.functions import HttpResponse

from .adapter import PydanticAdapter, ValidationAdapter
from .registry import GlobalErrorHandlerRegistry

ErrorFormatter = Callable[[Exception, int], dict[str, Any]]


def validate_http(
    *,
    body: Optional[Any] = None,
    query: Optional[Any] = None,
    path: Optional[Any] = None,
    headers: Optional[Any] = None,
    request_model: Optional[Any] = None,
    response_model: Optional[Any] = None,
    adapter: Optional[ValidationAdapter] = None,
    error_formatter: Optional["ErrorFormatter"] = None,
) -> Callable[..., Any]:
    # Handle request_model shorthand
    if request_model is not None:
        if any([body, query, path, headers]):
            raise ValueError("Cannot use request_model together with body/query/path/headers")
        body = request_model

    # Use default adapter if none provided
    if adapter is None:
        adapter = PydanticAdapter()

    def format_error_response(exception: Exception, status_code: int) -> HttpResponse:
        if error_formatter is not None:
            error_response = error_formatter(exception, status_code)
        else:
            global_handler = GlobalErrorHandlerRegistry.get_handler(exception)
            if global_handler is not None:
                return global_handler(exception)
            error_response = adapter.format_error(exception)

        return HttpResponse(
            body=json.dumps(error_response),
            status_code=status_code,
            headers={"Content-Type": "application/json"},
        )

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        # Check if function is async
        is_async = inspect.iscoroutinefunction(func)

        # Get function signature to validate parameters
        func_sig = inspect.signature(func)
        func_params = func_sig.parameters

        # Validate that function accepts HttpRequest
        has_http_request_param = any(
            param_name in ["req", "http_request"] for param_name in func_params.keys()
        )

        if not has_http_request_param:
            raise ValueError(
                f"Function {func.__name__} must accept an HttpRequest parameter "
                f"(parameter name should be 'req' or 'http_request')"
            )

        def wrapper(*args: Any, **kwargs: Any) -> HttpResponse:
            # Extract HttpRequest from args
            http_request = None
            for arg in args:
                # Check for HttpRequest or duck typing
                if (
                    hasattr(arg, "method")
                    and hasattr(arg, "url")
                    and hasattr(arg, "get_body")
                    and hasattr(arg, "headers")
                ):
                    http_request = arg
                    break

            if http_request is None:
                raise ValueError("Function must receive an HttpRequest-like object as argument")

            try:
                # Parse and validate request inputs
                parsed_inputs = {}

                # Parse body
                if body is not None:
                    try:
                        parsed_body = adapter.parse_body(http_request, body)

                        # Check if handler expects the 'body' parameter
                        if "body" in func_params:
                            parsed_inputs["body"] = parsed_body
                        elif "req_model" in func_params and request_model is not None:
                            # Handle request_model shorthand parameter name
                            parsed_inputs["req_model"] = parsed_body
                        else:
                            # Try to find parameter name that matches
                            for param_name in func_params:
                                if (
                                    param_name not in ["http_request", "req"]
                                    and param_name != "http_request"
                                ):
                                    parsed_inputs[param_name] = parsed_body
                                    break

                    except Exception as e:
                        from pydantic import ValidationError as PydanticValidationError

                        if isinstance(e, PydanticValidationError):
                            return format_error_response(e, 422)
                        elif isinstance(e, ValueError):
                            return format_error_response(e, 400)
                        else:
                            return format_error_response(e, 422)

                # Parse query parameters
                if query is not None:
                    try:
                        # Always validate query parameters, even if function doesn't use them
                        adapter.parse_query(http_request, query)
                        # If function expects query parameter, pass it
                        if "query" in func_params:
                            parsed_inputs["query"] = adapter.parse_query(http_request, query)
                    except Exception as e:
                        return format_error_response(e, 422)

                # Parse path parameters
                if path is not None:
                    try:
                        # Always validate path parameters, even if function doesn't use them
                        adapter.parse_path(http_request, path)
                        # If function expects path parameter, pass it
                        if "path" in func_params:
                            parsed_inputs["path"] = adapter.parse_path(http_request, path)
                    except Exception as e:
                        return format_error_response(e, 422)

                # Parse headers
                if headers is not None:
                    try:
                        # Always validate headers, even if function doesn't use them
                        adapter.parse_headers(http_request, headers)
                        # If function expects headers parameter, pass it
                        if "headers" in func_params:
                            parsed_inputs["headers"] = adapter.parse_headers(http_request, headers)
                    except Exception as e:
                        return format_error_response(e, 422)

                # Add original HttpRequest if requested
                if "http_request" in func_params:
                    parsed_inputs["http_request"] = http_request

                # Call the function
                if is_async:
                    import asyncio

                    result = asyncio.run(func(http_request, **parsed_inputs))
                else:
                    result = func(http_request, **parsed_inputs)

                # Handle HttpResponse bypass
                if isinstance(result, HttpResponse):
                    return result

                # Validate and serialize response
                if response_model is not None:
                    try:
                        validated_result = adapter.validate_response(result, response_model)
                        content, content_type = adapter.serialize(validated_result)
                        return HttpResponse(
                            body=content, status_code=200, headers={"Content-Type": content_type}
                        )
                    except Exception as e:
                        if error_formatter is not None:
                            error_response = error_formatter(e, 500)
                        else:
                            error_response = {
                                "detail": [
                                    {
                                        "loc": ["response"],
                                        "msg": "Response validation error",
                                        "type": "response_validation_error",
                                    }
                                ]
                            }
                        return HttpResponse(
                            body=json.dumps(error_response),
                            status_code=500,
                            headers={"Content-Type": "application/json"},
                        )
                else:
                    # No response model, serialize directly
                    content, content_type = adapter.serialize(result)
                    return HttpResponse(
                        body=content, status_code=200, headers={"Content-Type": content_type}
                    )

            except Exception as e:
                return format_error_response(e, 500)

        return wrapper

    return decorator
