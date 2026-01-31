"""Core decorator for HTTP request/response validation."""

import inspect
import json
from typing import Any, Callable, Optional

from azure.functions import HttpResponse

from .adapter import PydanticAdapter, ValidationAdapter


def validate_http(
    *,
    body: Optional[Any] = None,
    query: Optional[Any] = None,
    path: Optional[Any] = None,
    headers: Optional[Any] = None,
    request_model: Optional[Any] = None,
    response_model: Optional[Any] = None,
    adapter: Optional[ValidationAdapter] = None,
) -> Callable[..., Any]:
    """Decorator for validating HTTP requests and responses in Azure Functions.

    Args:
        body: Model class for request body validation
        query: Model class for query parameter validation
        path: Model class for path parameter validation
        headers: Model class for header validation
        request_model: Shorthand for body model only (alias for body)
        response_model: Model class for response validation
        adapter: Validation adapter instance (defaults to PydanticAdapter)

    Returns:
        Decorator function

    Raises:
        ValueError: If both request_model and body/query/path/headers are provided
    """
    # Handle request_model shorthand
    if request_model is not None:
        if any([body, query, path, headers]):
            raise ValueError("Cannot use request_model together with body/query/path/headers")
        body = request_model

    # Use default adapter if none provided
    if adapter is None:
        adapter = PydanticAdapter()

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
                        # Handle different types of errors
                        from pydantic import ValidationError as PydanticValidationError

                        if isinstance(e, PydanticValidationError):
                            # Pydantic validation error - return 422
                            error_response = adapter.format_error(e)
                            return HttpResponse(
                                body=json.dumps(error_response),
                                status_code=422,
                                headers={"Content-Type": "application/json"},
                            )
                        elif isinstance(e, ValueError):
                            # JSON parsing error - return 400
                            error_response = adapter.format_error(e)
                            return HttpResponse(
                                body=json.dumps(error_response),
                                status_code=400,
                                headers={"Content-Type": "application/json"},
                            )
                        else:
                            # Other validation error - return 422
                            error_response = adapter.format_error(e)
                            return HttpResponse(
                                body=json.dumps(error_response),
                                status_code=422,
                                headers={"Content-Type": "application/json"},
                            )

                # Parse query parameters
                if query is not None:
                    try:
                        # Always validate query parameters, even if function doesn't use them
                        adapter.parse_query(http_request, query)
                        # If function expects query parameter, pass it
                        if "query" in func_params:
                            parsed_inputs["query"] = adapter.parse_query(http_request, query)
                    except Exception as e:
                        error_response = adapter.format_error(e)
                        return HttpResponse(
                            body=json.dumps(error_response),
                            status_code=422,
                            headers={"Content-Type": "application/json"},
                        )

                # Parse path parameters
                if path is not None:
                    try:
                        # Always validate path parameters, even if function doesn't use them
                        adapter.parse_path(http_request, path)
                        # If function expects path parameter, pass it
                        if "path" in func_params:
                            parsed_inputs["path"] = adapter.parse_path(http_request, path)
                    except Exception as e:
                        error_response = adapter.format_error(e)
                        return HttpResponse(
                            body=json.dumps(error_response),
                            status_code=422,
                            headers={"Content-Type": "application/json"},
                        )

                # Parse headers
                if headers is not None:
                    try:
                        # Always validate headers, even if function doesn't use them
                        adapter.parse_headers(http_request, headers)
                        # If function expects headers parameter, pass it
                        if "headers" in func_params:
                            parsed_inputs["headers"] = adapter.parse_headers(http_request, headers)
                    except Exception as e:
                        error_response = adapter.format_error(e)
                        return HttpResponse(
                            body=json.dumps(error_response),
                            status_code=422,
                            headers={"Content-Type": "application/json"},
                        )

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
                    except Exception:
                        # Response validation error - return 500
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
                # Unhandled exception - return 500
                error_response = adapter.format_error(e)
                return HttpResponse(
                    body=json.dumps(error_response),
                    status_code=500,
                    headers={"Content-Type": "application/json"},
                )

        return wrapper

    return decorator
