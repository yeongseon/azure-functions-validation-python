"""HTTP validation decorator for Azure Functions."""

import asyncio
from functools import wraps
import json
from typing import Any, Callable, Optional, TypeVar

from azure.functions import HttpRequest, HttpResponse
from pydantic import BaseModel, ValidationError

from .adapter import PydanticAdapter
from .exceptions import ResponseValidationError

# Type variable for generic function signatures
F = TypeVar("F", bound=Callable[..., Any])


def validate_http(
    body: Optional[type[BaseModel]] = None,
    request_model: Optional[type[BaseModel]] = None,
    response_model: Optional[type[BaseModel]] = None,
) -> Callable[[F], F]:
    """Decorator to validate HTTP requests and responses for Azure Functions.

    Args:
        body: Pydantic model for request body validation
        request_model: Shorthand for body validation (cannot be used with body)
        response_model: Pydantic model for response validation

    Returns:
        Decorated function with validation

    Raises:
        ValueError: If both body and request_model are specified

    Example:
        @validate_http(request_model=MyRequest, response_model=MyResponse)
        def main(req: MyRequest) -> MyResponse:
            return MyResponse(message=f"Hello {req.name}")
    """
    # Validate configuration - cannot specify both body and request_model
    if body is not None and request_model is not None:
        raise ValueError("Cannot specify both 'body' and 'request_model'")

    # Use request_model as body if specified
    body_model = body or request_model

    # Create adapter instance
    adapter = PydanticAdapter()

    def decorator(func: F) -> F:
        # Determine if function is async
        is_async = asyncio.iscoroutinefunction(func)

        if is_async:

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> HttpResponse:
                return await _process_request_async(
                    func, args, kwargs, body_model, response_model, adapter
                )

            return async_wrapper  # type: ignore

        else:

            @wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> HttpResponse:
                return _process_request(func, args, kwargs, body_model, response_model, adapter)

            return sync_wrapper  # type: ignore

    return decorator


def _process_request(
    func: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    body_model: Optional[type[BaseModel]],
    response_model: Optional[type[BaseModel]],
    adapter: PydanticAdapter,
) -> HttpResponse:
    """Process HTTP request with validation.

    Args:
        func: Handler function to call
        args: Positional arguments
        kwargs: Keyword arguments
        body_model: Model for body validation
        response_model: Model for response validation
        adapter: Validation adapter

    Returns:
        HttpResponse object
    """
    try:
        # Find HttpRequest in arguments
        http_request = _find_http_request(args, kwargs)

        if http_request is None:
            raise ValueError("HttpRequest not found in function arguments")

        # Parse and validate request body if model is specified
        if body_model is not None:
            try:
                validated_body = adapter.parse_body(http_request, body_model)
            except ValidationError as e:
                # Validation error - return 422 (must catch before ValueError!)
                error_response = adapter.format_error(e)
                return HttpResponse(
                    body=json.dumps(error_response),
                    status_code=422,
                    mimetype="application/json",
                )
            except ValueError as e:
                # Invalid JSON - return 400
                error_response = adapter.format_error(e)
                return HttpResponse(
                    body=json.dumps(error_response),
                    status_code=400,
                    mimetype="application/json",
                )

            # Inject validated model into arguments
            new_args, new_kwargs = _inject_validated_model(
                args, kwargs, validated_body, http_request
            )
        else:
            # No body validation - use original arguments
            new_args, new_kwargs = args, kwargs

        # Call handler function
        result = func(*new_args, **new_kwargs)

        # Handle response
        return _process_response(result, response_model, adapter)

    except ResponseValidationError as e:
        # Response validation error - return 500
        error_response = adapter.format_error(e)
        return HttpResponse(
            body=json.dumps(error_response),
            status_code=500,
            mimetype="application/json",
        )
    except Exception:
        # Let other exceptions propagate
        raise


async def _process_request_async(
    func: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    body_model: Optional[type[BaseModel]],
    response_model: Optional[type[BaseModel]],
    adapter: PydanticAdapter,
) -> HttpResponse:
    """Process HTTP request with validation (async version).

    Args:
        func: Async handler function to call
        args: Positional arguments
        kwargs: Keyword arguments
        body_model: Model for body validation
        response_model: Model for response validation
        adapter: Validation adapter

    Returns:
        HttpResponse object
    """
    try:
        # Find HttpRequest in arguments
        http_request = _find_http_request(args, kwargs)

        if http_request is None:
            raise ValueError("HttpRequest not found in function arguments")

        # Parse and validate request body if model is specified
        if body_model is not None:
            try:
                validated_body = adapter.parse_body(http_request, body_model)
            except ValidationError as e:
                # Validation error - return 422 (must catch before ValueError!)
                error_response = adapter.format_error(e)
                return HttpResponse(
                    body=json.dumps(error_response),
                    status_code=422,
                    mimetype="application/json",
                )
            except ValueError as e:
                # Invalid JSON - return 400
                error_response = adapter.format_error(e)
                return HttpResponse(
                    body=json.dumps(error_response),
                    status_code=400,
                    mimetype="application/json",
                )

            # Inject validated model into arguments
            new_args, new_kwargs = _inject_validated_model(
                args, kwargs, validated_body, http_request
            )
        else:
            # No body validation - use original arguments
            new_args, new_kwargs = args, kwargs

        # Call async handler function
        result = await func(*new_args, **new_kwargs)

        # Handle response
        return _process_response(result, response_model, adapter)

    except ResponseValidationError as e:
        # Response validation error - return 500
        error_response = adapter.format_error(e)
        return HttpResponse(
            body=json.dumps(error_response),
            status_code=500,
            mimetype="application/json",
        )
    except Exception:
        # Let other exceptions propagate
        raise


def _find_http_request(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Optional[HttpRequest]:
    """Find HttpRequest in function arguments.

    Args:
        args: Positional arguments
        kwargs: Keyword arguments

    Returns:
        HttpRequest instance or None
    """
    # Check positional arguments
    for arg in args:
        if isinstance(arg, HttpRequest):
            return arg

    # Check keyword arguments
    for value in kwargs.values():
        if isinstance(value, HttpRequest):
            return value

    return None


def _inject_validated_model(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    validated_model: BaseModel,
    http_request: HttpRequest,
) -> tuple[tuple[Any, ...], dict[str, Any]]:
    """Inject validated model into function arguments.

    Replaces the HttpRequest with the validated model, keeping HttpRequest
    available if it's explicitly requested by parameter name.

    Args:
        args: Original positional arguments
        kwargs: Original keyword arguments
        validated_model: Validated model instance
        http_request: Original HttpRequest

    Returns:
        Tuple of (new_args, new_kwargs)
    """
    # Convert args to list for modification
    new_args = list(args)

    # Find and replace HttpRequest with validated model in positional args
    for i, arg in enumerate(new_args):
        if isinstance(arg, HttpRequest):
            new_args[i] = validated_model
            break

    # Keep kwargs as-is but inject validated model as first positional arg if not found
    if not any(isinstance(arg, HttpRequest) for arg in args):
        # HttpRequest was in kwargs, replace first arg
        new_args = [validated_model] + new_args

    # Check if function expects http_request parameter
    # If so, add it to kwargs
    new_kwargs = kwargs.copy()
    if "http_request" in new_kwargs or any(
        k in ["http_request", "request"] for k in new_kwargs.keys()
    ):
        new_kwargs["http_request"] = http_request

    return tuple(new_args), new_kwargs


def _process_response(
    result: Any, response_model: Optional[type[BaseModel]], adapter: PydanticAdapter
) -> HttpResponse:
    """Process handler response.

    Args:
        result: Handler return value
        response_model: Optional response model for validation
        adapter: Validation adapter

    Returns:
        HttpResponse object
    """
    # If result is already HttpResponse, pass through
    if isinstance(result, HttpResponse):
        return result

    # If response_model is specified, validate
    if response_model is not None:
        validated_response = adapter.validate_response(result, response_model)
        content, content_type = adapter.serialize(validated_response)
    else:
        # No validation, just serialize
        content, content_type = adapter.serialize(result)

    return HttpResponse(body=content, mimetype=content_type, status_code=200)
