"""Main validate_http decorator implementation."""

from functools import wraps
import inspect
from typing import Any, Callable, TypeVar

from azure.functions import HttpRequest, HttpResponse
from pydantic import BaseModel, ValidationError

from ._adapter import PydanticAdapter

F = TypeVar("F", bound=Callable[..., Any])


class ResponseValidationError(Exception):
    """Raised when response validation fails."""

    pass


def validate_http(
    *,
    request_model: type[BaseModel] | None = None,
    body: type[BaseModel] | None = None,
    response_model: type[BaseModel] | None = None,
) -> Callable[[F], F]:
    """
    Decorator for validating Azure Functions HTTP requests and responses.

    Args:
        request_model: Shorthand for body model (for backward compatibility).
        body: Body model for request validation.
        response_model: Response model for response validation.

    Returns:
        Decorated function with validation.

    Raises:
        ValueError: If configuration is invalid.

    Example:
        ```python
        @validate_http(body=MyRequest, response_model=MyResponse)
        def main(body: MyRequest) -> MyResponse:
            return MyResponse(message=f"Hello {body.name}")
        ```
    """
    # Validate configuration
    if request_model and body:
        raise ValueError("Cannot specify both 'request_model' and 'body'")

    # Normalize: request_model is shorthand for body
    body_model = body or request_model

    adapter = PydanticAdapter()

    def decorator(func: F) -> F:
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> HttpResponse:
            return _process_request(func, args, kwargs, body_model, response_model, adapter)

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> HttpResponse:
            return await _process_request_async(
                func, args, kwargs, body_model, response_model, adapter
            )

        # Return appropriate wrapper based on function type
        if inspect.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


def _process_request(
    func: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    body_model: type[BaseModel] | None,
    response_model: type[BaseModel] | None,
    adapter: PydanticAdapter,
) -> HttpResponse:
    """Process request synchronously."""
    try:
        # Find HttpRequest in args
        http_request = _find_http_request(args, kwargs)
        if not http_request:
            raise ValueError("HttpRequest not found in function arguments")

        # Parse and validate body if body_model is specified
        validated_args, validated_kwargs = _prepare_handler_args(
            func, args, kwargs, http_request, body_model, adapter
        )

        # Call the handler
        result = func(*validated_args, **validated_kwargs)

        # If handler returns HttpResponse, pass through
        if isinstance(result, HttpResponse):
            return result

        # Validate and serialize response
        return _build_response(result, response_model, adapter)

    except ValidationError as e:
        # Request validation error (422)
        error_dict = adapter.format_error(e)
        return _build_error_response(error_dict, 422)
    except ValueError as e:
        # JSON parsing error (400)
        if "Invalid JSON" in str(e):
            return _build_error_response(
                {"detail": [{"loc": ["body"], "msg": "Invalid JSON", "type": "json_invalid"}]},
                400,
            )
        raise
    except ResponseValidationError:
        # Response validation error (500)
        return _build_error_response(
            {
                "detail": [
                    {
                        "loc": ["response"],
                        "msg": "Response validation error",
                        "type": "response_validation_error",
                    }
                ]
            },
            500,
        )
    except Exception:
        # Let other exceptions propagate (Azure Functions will handle them)
        raise


async def _process_request_async(
    func: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    body_model: type[BaseModel] | None,
    response_model: type[BaseModel] | None,
    adapter: PydanticAdapter,
) -> HttpResponse:
    """Process request asynchronously."""
    try:
        # Find HttpRequest in args
        http_request = _find_http_request(args, kwargs)
        if not http_request:
            raise ValueError("HttpRequest not found in function arguments")

        # Parse and validate body if body_model is specified
        validated_args, validated_kwargs = _prepare_handler_args(
            func, args, kwargs, http_request, body_model, adapter
        )

        # Call the async handler
        result = await func(*validated_args, **validated_kwargs)

        # If handler returns HttpResponse, pass through
        if isinstance(result, HttpResponse):
            return result

        # Validate and serialize response
        return _build_response(result, response_model, adapter)

    except ValidationError as e:
        # Request validation error (422)
        error_dict = adapter.format_error(e)
        return _build_error_response(error_dict, 422)
    except ValueError as e:
        # JSON parsing error (400)
        if "Invalid JSON" in str(e):
            return _build_error_response(
                {"detail": [{"loc": ["body"], "msg": "Invalid JSON", "type": "json_invalid"}]},
                400,
            )
        raise
    except ResponseValidationError:
        # Response validation error (500)
        return _build_error_response(
            {
                "detail": [
                    {
                        "loc": ["response"],
                        "msg": "Response validation error",
                        "type": "response_validation_error",
                    }
                ]
            },
            500,
        )
    except Exception:
        # Let other exceptions propagate (Azure Functions will handle them)
        raise


def _find_http_request(args: tuple[Any, ...], kwargs: dict[str, Any]) -> HttpRequest | None:
    """Find HttpRequest in function arguments."""
    # Check kwargs first
    for value in kwargs.values():
        if isinstance(value, HttpRequest):
            return value

    # Check args
    for arg in args:
        if isinstance(arg, HttpRequest):
            return arg

    return None


def _prepare_handler_args(
    func: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    http_request: HttpRequest,
    body_model: type[BaseModel] | None,
    adapter: PydanticAdapter,
) -> tuple[tuple[Any, ...], dict[str, Any]]:
    """Prepare handler arguments with validated models."""
    sig = inspect.signature(func)
    param_names = list(sig.parameters.keys())

    # Parse body if body_model is specified
    validated_body = None
    if body_model:
        validated_body = adapter.parse_body(http_request, body_model)

    # If no body model, pass through original arguments
    if validated_body is None:
        return args, kwargs

    # Find where to inject the validated body
    new_args = []
    new_kwargs = dict(kwargs)

    for i, param_name in enumerate(param_names):
        param = sig.parameters[param_name]

        # Check if this parameter should receive the validated body
        if param.annotation == body_model or param_name in ("body", "req"):
            if i < len(args):
                # Replace the arg at this position
                new_args.append(validated_body)
            else:
                # Add to kwargs
                new_kwargs[param_name] = validated_body
        elif param.annotation == HttpRequest or param_name == "http_request":
            # Make HttpRequest available
            if i < len(args):
                new_args.append(http_request)
            else:
                new_kwargs[param_name] = http_request
        else:
            # Keep original arg if available
            if i < len(args):
                new_args.append(args[i])

    return tuple(new_args), new_kwargs


def _build_response(
    result: Any, response_model: type[BaseModel] | None, adapter: PydanticAdapter
) -> HttpResponse:
    """Build HttpResponse from handler result."""
    try:
        # Validate response if response_model is specified
        if response_model:
            validated_result = adapter.validate_response(result, response_model)
            content, content_type = adapter.serialize(validated_result)
        else:
            content, content_type = adapter.serialize(result)

        # Build HttpResponse
        if isinstance(content, str):
            return HttpResponse(body=content, mimetype=content_type, status_code=200)
        return HttpResponse(body=content, mimetype=content_type, status_code=200)

    except (TypeError, ValidationError) as e:
        raise ResponseValidationError(str(e)) from e


def _build_error_response(error_dict: dict[str, Any], status_code: int) -> HttpResponse:
    """Build error HttpResponse."""
    import json

    body = json.dumps(error_dict)
    return HttpResponse(body=body, mimetype="application/json", status_code=status_code)
