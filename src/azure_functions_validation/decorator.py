"""Core decorator for HTTP request/response validation."""

from functools import wraps
import inspect
import json
from typing import Any, Callable, Optional

from azure.functions import HttpResponse

from .adapter import PydanticAdapter, ValidationAdapter
from .exceptions import ResponseValidationError
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

        # Validate that function can accept the request as its first positional argument.
        request_param_name = next(
            (
                param_name
                for param_name, param in func_params.items()
                if param.kind
                in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                )
            ),
            None,
        )

        if request_param_name is None:
            raise ValueError(
                f"Function {func.__name__} must accept an HttpRequest parameter "
                f"as its first positional argument"
            )

        # Guard against first positional parameter name conflicting with injected parameter names.
        # If the request param shares a name with an injected input (body/query/path/headers/req_model),
        # the wrapper would call func(http_request, body=parsed_body) causing TypeError at runtime.
        _injected: dict[str, Any] = {
            "body": body,
            "query": query,
            "path": path,
            "headers": headers,
            "req_model": request_model,
        }
        if request_param_name in _injected and _injected[request_param_name] is not None:
            raise ValueError(
                f"Function {func.__name__}: first positional parameter '{request_param_name}' "
                f"conflicts with a @validate_http injected parameter of the same name. "
                f"Rename it (e.g. to 'req' or 'http_request')."
            )

        def resolve_http_request(args: tuple[Any, ...]) -> Any:
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

            return http_request

        def parse_inputs(http_request: Any) -> dict[str, Any] | HttpResponse:
            # Parse and validate request inputs
            parsed_inputs: dict[str, Any] = {}

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
                        # Try to find a parameter that is not the request, not http_request,
                        # and not a name used by another configured validation source
                        reserved_names = {request_param_name, "http_request"}
                        if query is not None:
                            reserved_names.add("query")
                        if path is not None:
                            reserved_names.add("path")
                        if headers is not None:
                            reserved_names.add("headers")
                        for param_name in func_params:
                            if param_name not in reserved_names:
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
                    parsed_query = adapter.parse_query(http_request, query)
                    # If function expects query parameter, pass it
                    if "query" in func_params:
                        parsed_inputs["query"] = parsed_query
                except Exception as e:
                    return format_error_response(e, 422)

            # Parse path parameters
            if path is not None:
                try:
                    # Always validate path parameters, even if function doesn't use them
                    parsed_path = adapter.parse_path(http_request, path)
                    # If function expects path parameter, pass it
                    if "path" in func_params:
                        parsed_inputs["path"] = parsed_path
                except Exception as e:
                    return format_error_response(e, 422)

            # Parse headers
            if headers is not None:
                try:
                    # Always validate headers, even if function doesn't use them
                    parsed_headers = adapter.parse_headers(http_request, headers)
                    # If function expects headers parameter, pass it
                    if "headers" in func_params:
                        parsed_inputs["headers"] = parsed_headers
                except Exception as e:
                    return format_error_response(e, 422)

            # Add original HttpRequest if requested
            if "http_request" in func_params and request_param_name != "http_request":
                parsed_inputs["http_request"] = http_request

            return parsed_inputs

        def build_response(result: Any) -> HttpResponse:
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
                    response_error = ResponseValidationError(
                        f"Response validation failed: {e}"
                    )
                    # Check global error handler first
                    global_handler = GlobalErrorHandlerRegistry.get_handler(response_error)
                    if global_handler is not None:
                        return global_handler(response_error)
                    if error_formatter is not None:
                        error_response = error_formatter(response_error, 500)
                    else:
                        error_response = {
                            "detail": [
                                {
                                    "loc": ["response"],
                                    "msg": str(response_error),
                                    "type": "response_validation_error",
                                }
                            ]
                        }
                    return HttpResponse(
                        body=json.dumps(error_response),
                        status_code=500,
                        headers={"Content-Type": "application/json"},
                    )

            # No response model, serialize directly
            content, content_type = adapter.serialize(result)
            return HttpResponse(
                body=content,
                status_code=200,
                headers={"Content-Type": content_type},
            )

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> HttpResponse:
            http_request = resolve_http_request(args)
            parsed_inputs = parse_inputs(http_request)
            if isinstance(parsed_inputs, HttpResponse):
                return parsed_inputs

            result = func(http_request, **parsed_inputs, **kwargs)
            return build_response(result)

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> HttpResponse:
            http_request = resolve_http_request(args)
            parsed_inputs = parse_inputs(http_request)
            if isinstance(parsed_inputs, HttpResponse):
                return parsed_inputs

            result = await func(http_request, **parsed_inputs, **kwargs)
            return build_response(result)

        return async_wrapper if is_async else wrapper

    return decorator
