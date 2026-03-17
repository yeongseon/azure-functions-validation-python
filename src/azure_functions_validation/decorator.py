"""Core decorator for HTTP request/response validation."""

from __future__ import annotations

import inspect
from typing import Any, Callable, Mapping

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

        return _make_wrapper(func, config, is_async=is_async)

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


_MISSING: Any = object()  # sentinel for absent req argument


def _make_wrapper(
    func: Callable[..., Any],
    config: Any,
    *,
    is_async: bool,
) -> Callable[..., Any]:
    """Return a wrapper whose visible signature satisfies the Azure Functions worker.

    The worker (``index_function_app`` / ``loader.py``) inspects ``co_argcount``
    and ``co_varnames`` on the registered callable to locate the HTTP trigger
    parameter.  A ``*args``/``**kwargs``-only wrapper has ``co_argcount == 0``
    and is silently skipped — producing an empty function list on the deployed app.

    We declare a real ``req`` positional parameter (``co_argcount == 1``) so the
    worker recognises the handler.  Callers may also pass the request via its
    *original* parameter name as a keyword argument (e.g. ``handler(request=r)``).
    In that case ``req`` receives a sentinel value and we look up the real object
    from ``**_kw`` using ``config.request_param_name``.

    ``functools.update_wrapper`` is intentionally **not** used because it sets
    ``__wrapped__ = func``, and some Azure Functions worker builds follow
    ``__wrapped__`` to the original function — seeing ``co_argcount > 1`` and
    failing to register the handler.  We copy only the safe metadata attributes.
    """
    orig_name: str = config.request_param_name or "req"

    if is_async:
        async def _async_wrapper(  # noqa: ANN202
            req: Any = _MISSING, **_kw: Any
        ) -> Any:  # noqa: ANN401
            _req = _kw.pop(orig_name, req) if req is _MISSING else req
            return await run_pipeline_async(func, (_req,), _kw, config)

        wrapper: Callable[..., Any] = _async_wrapper
    else:
        def _sync_wrapper(  # noqa: ANN202
            req: Any = _MISSING, **_kw: Any
        ) -> Any:  # noqa: ANN401
            _req = _kw.pop(orig_name, req) if req is _MISSING else req
            return run_pipeline(func, (_req,), _kw, config)

        wrapper = _sync_wrapper

    # Copy safe metadata attributes without setting __wrapped__.
    _COPY_ATTRS = (
        "__name__", "__qualname__", "__doc__", "__dict__", "__module__", "__annotations__",
    )
    for attr in _COPY_ATTRS:
        try:
            object.__setattr__(wrapper, attr, getattr(func, attr))
        except (AttributeError, TypeError):  # pragma: no cover
            pass
    return wrapper
