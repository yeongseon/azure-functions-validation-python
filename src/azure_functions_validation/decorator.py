"""Core decorator for HTTP request/response validation."""

from __future__ import annotations

from functools import wraps
import inspect
from typing import Any, Callable, Mapping

from azure.functions import HttpResponse

from .adapter import PydanticAdapter, ValidationAdapter
from .errors import ErrorFormatter
from .pipeline import PipelineConfig, run_pipeline, run_pipeline_async


def validate_http(
    *,
    body: Any = None,
    query: Any = None,
    path: Any = None,
    headers: Any = None,
    request_model: Any = None,
    response_model: Any = None,
    adapter: ValidationAdapter | None = None,
    error_formatter: ErrorFormatter | None = None,
) -> Callable[..., Any]:
    """Decorator for validating HTTP request inputs and response outputs.

    Args:
        body: Pydantic model for request body validation.
        query: Pydantic model for query parameter validation.
        path: Pydantic model for path parameter validation.
        headers: Pydantic model for header validation.
        request_model: Shorthand alias for *body*.
        response_model: Pydantic model for response validation.
        adapter: Custom validation adapter (defaults to ``PydanticAdapter``).
        error_formatter: Per-handler custom error formatter.

    Returns:
        A decorator that wraps the handler with validation logic.
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
        is_async = inspect.iscoroutinefunction(func)

        func_sig = inspect.signature(func)
        func_params = func_sig.parameters

        request_param_name = _find_request_param(func, func_params)
        _validate_no_conflicts(func, request_param_name, body, query, path, headers, request_model)

        config = PipelineConfig(
            body=body,
            query=query,
            path=path,
            headers=headers,
            request_model=request_model,
            response_model=response_model,
            adapter=adapter,
            error_formatter=error_formatter,
            func_params=func_params,
            request_param_name=request_param_name,
        )

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> HttpResponse:
            return run_pipeline(func, args, kwargs, config)

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> HttpResponse:
            return await run_pipeline_async(func, args, kwargs, config)

        return async_wrapper if is_async else wrapper

    return decorator


# ---------------------------------------------------------------------------
# Decorator-time helpers (configuration validation, not request processing)
# ---------------------------------------------------------------------------


def _find_request_param(
    func: Callable[..., Any],
    func_params: Mapping[str, inspect.Parameter],
) -> str:
    """Find the first positional parameter name (the HttpRequest slot).

    Raises:
        ValueError: If no positional parameter exists.
    """
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

    return request_param_name


def _validate_no_conflicts(
    func: Callable[..., Any],
    request_param_name: str,
    body: Any,
    query: Any,
    path: Any,
    headers: Any,
    request_model: Any,
) -> None:
    """Raise ``ValueError`` if the first positional parameter name collides
    with an injected parameter name.
    """
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
