"""Validation pipeline engine.

This module contains the request-parsing and response-building logic that was
previously inlined inside the ``validate_http`` decorator closure.  Extracting
it into standalone functions makes the pipeline independently testable and
keeps ``decorator.py`` focused on configuration and wiring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from azure.functions import HttpResponse

from .adapter import PydanticAdapter, ValidationAdapter
from .errors import (
    AdapterValidationError,
    ErrorFormatter,
    ResponseValidationError,
    SerializationError,
    format_error_response,
)


@dataclass(frozen=True)
class PipelineConfig:
    """Internal configuration for the validation pipeline.

    Created once by the ``validate_http`` decorator and reused on every
    invocation.  All fields are immutable after construction.
    """

    body: Any = None
    query: Any = None
    path: Any = None
    headers: Any = None
    request_model: Any = None
    response_model: Any = None
    adapter: ValidationAdapter = field(default_factory=PydanticAdapter)
    error_formatter: ErrorFormatter | None = None
    func_params: Mapping[str, Any] = field(default_factory=dict)
    request_param_name: str | None = None
    response_type_adapter: Any = None


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def _prepare_invocation(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    config: PipelineConfig,
) -> tuple[HttpResponse | None, dict[str, Any]]:
    """Resolve the request and parse inputs shared by both pipelines.

    Returns a ``(early_response, merged_kwargs)`` pair.  When *early_response*
    is not ``None`` the caller must return it immediately without invoking the
    handler (request resolution or input validation failed).
    """
    try:
        http_request = _resolve_http_request(args, kwargs, config)
    except ValueError as e:
        return format_error_response(e, 400, config.adapter, config.error_formatter), {}
    parsed = _parse_inputs(http_request, config)
    if isinstance(parsed, HttpResponse):
        return parsed, {}
    merged = _merge_kwargs(args, kwargs, parsed)
    return None, merged


def run_pipeline(
    func: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    config: PipelineConfig,
) -> HttpResponse:
    """Execute the sync validation pipeline."""
    early, merged = _prepare_invocation(args, kwargs, config)
    if early is not None:
        return early
    result = func(*args, **merged) if args else func(**merged)
    return _build_response(result, config)


async def run_pipeline_async(
    func: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    config: PipelineConfig,
) -> HttpResponse:
    """Execute the async validation pipeline."""
    early, merged = _prepare_invocation(args, kwargs, config)
    if early is not None:
        return early
    result = await (func(*args, **merged) if args else func(**merged))
    return _build_response(result, config)


# ---------------------------------------------------------------------------
# Private helpers (moved from decorator.py)
# ---------------------------------------------------------------------------


def _is_http_request_like(candidate: Any) -> bool:
    """Return ``True`` if *candidate* looks like an ``HttpRequest``."""
    return (
        hasattr(candidate, "method")
        and hasattr(candidate, "url")
        and hasattr(candidate, "get_body")
        and hasattr(candidate, "headers")
    )


def _resolve_http_request(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    config: PipelineConfig,
) -> Any:
    """Find the ``HttpRequest`` from positional or keyword arguments."""
    # Extract HttpRequest from positional args first
    for arg in args:
        if _is_http_request_like(arg):
            return arg

    # Prefer the declared request parameter name when invoked with kwargs
    if config.request_param_name is not None and _is_http_request_like(
        kwargs.get(config.request_param_name)
    ):
        return kwargs[config.request_param_name]

    # Support the explicit http_request alias too
    if config.request_param_name != "http_request" and _is_http_request_like(
        kwargs.get("http_request")
    ):
        return kwargs["http_request"]

    # Fall back to any HttpRequest-like keyword value
    for value in kwargs.values():
        if _is_http_request_like(value):
            return value

    raise ValueError("Function must receive an HttpRequest-like object as argument")


def _parse_inputs(
    http_request: Any,
    config: PipelineConfig,
) -> dict[str, Any] | HttpResponse:
    """Parse and validate all configured request inputs."""
    parsed_inputs: dict[str, Any] = {}

    # Parse body
    if config.body is not None:
        try:
            parsed_body = config.adapter.parse_body(http_request, config.body)

            # Inject body into the appropriate parameter
            if "body" in config.func_params:
                parsed_inputs["body"] = parsed_body
            elif "req_model" in config.func_params and config.request_model is not None:
                parsed_inputs["req_model"] = parsed_body
        except AdapterValidationError as e:
            return format_error_response(e, 422, config.adapter, config.error_formatter)
        except ValueError as e:
            return format_error_response(e, 400, config.adapter, config.error_formatter)
        except Exception as e:
            return format_error_response(e, 500, config.adapter, config.error_formatter)
    # Parse query parameters
    if config.query is not None:
        try:
            # Always validate query parameters, even if function doesn't use them
            parsed_query = config.adapter.parse_query(http_request, config.query)
            # If function expects query parameter, pass it
            if "query" in config.func_params:
                parsed_inputs["query"] = parsed_query
        except AdapterValidationError as e:
            return format_error_response(e, 422, config.adapter, config.error_formatter)
        except ValueError as e:
            return format_error_response(e, 400, config.adapter, config.error_formatter)
        except Exception as e:
            return format_error_response(e, 500, config.adapter, config.error_formatter)
    # Parse path parameters
    if config.path is not None:
        try:
            # Always validate path parameters, even if function doesn't use them
            parsed_path = config.adapter.parse_path(http_request, config.path)
            # If function expects path parameter, pass it
            if "path" in config.func_params:
                parsed_inputs["path"] = parsed_path
        except AdapterValidationError as e:
            return format_error_response(e, 422, config.adapter, config.error_formatter)
        except ValueError as e:
            return format_error_response(e, 400, config.adapter, config.error_formatter)
        except Exception as e:
            return format_error_response(e, 500, config.adapter, config.error_formatter)
    # Parse headers
    if config.headers is not None:
        try:
            # Always validate headers, even if function doesn't use them
            parsed_headers = config.adapter.parse_headers(http_request, config.headers)
            # If function expects headers parameter, pass it
            if "headers" in config.func_params:
                parsed_inputs["headers"] = parsed_headers
        except AdapterValidationError as e:
            return format_error_response(e, 422, config.adapter, config.error_formatter)
        except ValueError as e:
            return format_error_response(e, 400, config.adapter, config.error_formatter)
        except Exception as e:
            return format_error_response(e, 500, config.adapter, config.error_formatter)
    # Add original HttpRequest if requested
    if "http_request" in config.func_params and config.request_param_name != "http_request":
        parsed_inputs["http_request"] = http_request

    return parsed_inputs


def _merge_kwargs(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    parsed_inputs: dict[str, Any],
) -> dict[str, Any]:
    """Merge original kwargs with parsed/validated inputs.

    Removes keys from *kwargs* that would collide with *parsed_inputs* to
    avoid passing duplicate values to the wrapped function.
    """
    filtered_kwargs = {k: v for k, v in kwargs.items() if k not in parsed_inputs}
    return {**filtered_kwargs, **parsed_inputs}


def _build_response(result: Any, config: PipelineConfig) -> HttpResponse:
    """Validate and serialize the handler return value into an ``HttpResponse``."""
    # Handle HttpResponse bypass
    if isinstance(result, HttpResponse):
        return result

    # Handle None return → 204 No Content
    if result is None:
        return HttpResponse(status_code=204)

    # Validate and serialize response
    if config.response_model is not None:
        try:
            validated_result = config.adapter.validate_response(
                result, config.response_model, type_adapter=config.response_type_adapter
            )
        except AdapterValidationError:
            response_error = ResponseValidationError("Response validation failed")
            return format_error_response(
                response_error, 500, config.adapter, config.error_formatter,
            )
        except Exception:
            response_error = ResponseValidationError("Response validation failed")
            return format_error_response(
                response_error, 500, config.adapter, config.error_formatter,
            )

        try:
            content, content_type = config.adapter.serialize(validated_result)
        except (SerializationError, TypeError) as e:
            return format_error_response(
                e, 500, config.adapter, config.error_formatter,
            )

        return HttpResponse(
            body=content, status_code=200, headers={"Content-Type": content_type}
        )

    # No response model, serialize directly
    try:
        content, content_type = config.adapter.serialize(result)
    except (SerializationError, TypeError) as e:
        return format_error_response(
            e, 500, config.adapter, config.error_formatter,
        )

    return HttpResponse(
        body=content,
        status_code=200,
        headers={"Content-Type": content_type},
    )
