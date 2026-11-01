"""Error types and formatting for azure-functions-validation."""

from __future__ import annotations

from collections.abc import Callable
import json
import logging
from typing import Any, Protocol

from azure.functions import HttpResponse
from pydantic import TypeAdapter

from ._response_transport import build_response, json_media_type, validation_status
from .responses import ErrorResponseSpec, ValidationErrorResponse

logger = logging.getLogger(__name__)

ErrorFormatter = Callable[[Exception, int], dict[str, Any] | ErrorResponseSpec]

#: Stability marker embedded in every default error envelope.  Downstream
#: consumers can pin against this integer; it is bumped only when the default
#: error-response schema changes in a backwards-incompatible way.
ERROR_FORMAT_VERSION = 1

_SANITIZED_500_BODY = json.dumps(
    {
        "detail": [
            {
                "loc": [],
                "msg": "Internal Server Error",
                "type": "server_error",
            }
        ],
        "error_format_version": ERROR_FORMAT_VERSION,
    }
)


class InternalServerError(Exception):
    """Sanitized exception supplied to custom formatters for server errors."""

    def __init__(self) -> None:
        super().__init__("Internal Server Error")


class RequestBindingError(Exception):
    """Raised when the pipeline cannot resolve the handler's HTTP request."""


class MalformedRequestError(Exception):
    """Raised by adapters when client input is syntactically malformed."""


class PayloadTooLargeError(Exception):
    """Raised when a request body exceeds its configured byte limit."""

    def __init__(self) -> None:
        super().__init__("Request body too large")


class UnsupportedMediaTypeError(Exception):
    """Raised when a body endpoint requires JSON but receives another media type."""

    def __init__(self) -> None:
        super().__init__("Unsupported media type; expected application/json")


class ErrorAdapter(Protocol):
    def format_error(self, exc: Exception) -> dict[str, Any]: ...


class ResponseValidationError(Exception):
    """Raised when response validation fails."""

    def __init__(self, message: str = "Response validation error"):
        """Initialize ResponseValidationError.

        Args:
            message: Error message
        """
        super().__init__(message)
        self.message = message


class SerializationError(TypeError):
    """Raised when an unsupported type is encountered during serialization."""

    def __init__(self, type_name: str) -> None:
        """Initialize SerializationError.

        Args:
            type_name: Name of the unsupported type.
        """
        super().__init__(f"Cannot serialize type {type_name}")
        self.type_name = type_name


class HttpError(Exception):
    """Raised by a handler to return a controlled HTTP error response.

    Rendered through the standard error envelope (``{"detail": [...]}``) by the
    validation pipeline, so controlled errors (e.g. 404, 409) share the same
    shape as automatic validation errors.

    Args:
        status_code: HTTP status code for the response (e.g. ``404``).
        detail: Either a human-readable message (wrapped into a single
            ``{"loc": [], "msg": ..., "type": ...}`` entry) or a pre-built list
            of detail mappings matching the error-envelope schema.
        error_type: ``type`` value used when *detail* is a plain message.
    """

    def __init__(
        self,
        status_code: int,
        detail: Any = "Error",
        *,
        error_type: str = "http_error",
    ) -> None:
        super().__init__(str(detail))
        self.status_code = status_code
        self.detail = detail
        self.error_type = error_type

    def to_detail(self) -> list[dict[str, Any]]:
        """Return the error-envelope ``detail`` list for this error."""
        if isinstance(self.detail, list):
            return self.detail
        return [{"loc": [], "msg": str(self.detail), "type": self.error_type}]


class AdapterValidationError(Exception):
    """Raised by validation adapters when request/response validation fails.

    Decouples the pipeline and downstream callers from the underlying
    validation library (e.g. Pydantic).  The normalized ``errors`` list mirrors
    the public error-response ``detail`` schema: each entry is a mapping with
    ``loc`` (list), ``msg`` (str), and ``type`` (str) keys.
    """

    def __init__(self, message: str, errors: list[dict[str, Any]]) -> None:
        """Initialize AdapterValidationError.

        Args:
            message: Human-readable error message.
            errors: Normalized list of error detail mappings.
        """
        super().__init__(message)
        self.errors: list[dict[str, Any]] = errors


class AggregatedValidationError(AdapterValidationError):
    """Combined normalized errors from multiple request input sources."""

    def __init__(self, errors: list[dict[str, Any]]) -> None:
        super().__init__("Request validation failed", errors)


def format_error_response(
    exception: Exception,
    status_code: int,
    adapter: ErrorAdapter,
    error_formatter: ErrorFormatter | None = None,
    *,
    expose_internal_errors: bool = False,
    handler_name: str | None = None,
    log_exception: bool = True,
    request_validation: bool = False,
    validation_error_response: ValidationErrorResponse | None = None,
    error_type_adapter: TypeAdapter[Any] | None = None,
) -> HttpResponse:
    """Build an ``HttpResponse`` for a validation or parsing error.

    Args:
        exception: The caught exception.
        status_code: HTTP status code for the response.
        adapter: The validation adapter used for default formatting.
        error_formatter: Optional per-handler custom formatter.
        expose_internal_errors: Pass the original server-side exception to the
            custom formatter. This is unsafe because formatters may expose it.
        handler_name: Name of the handler associated with a server error.
        log_exception: Whether this function owns logging the server error.

    Returns:
        An ``HttpResponse`` with a JSON error body.
    """
    response_status_code = status_code
    used_custom_formatter = False

    if status_code >= 500 and log_exception:
        logger.error(
            "Server-side validation pipeline error for handler %r",
            handler_name,
            exc_info=exception,
        )

    formatter_exception = (
        exception if status_code < 500 or expose_internal_errors else InternalServerError()
    )

    if error_formatter is not None:
        try:
            error_response = error_formatter(formatter_exception, status_code)
        except Exception:
            logger.exception("error_formatter raised an unexpected exception")
            return _sanitized_response()
        else:
            used_custom_formatter = True
    elif isinstance(exception, HttpError) and status_code < 500:
        # Controlled handler error — render its detail through the envelope.
        error_response = {"detail": exception.to_detail()}
    elif isinstance(exception, PayloadTooLargeError):
        error_response = {
            "detail": [
                {
                    "loc": ["body"],
                    "msg": str(exception),
                    "type": "payload_too_large",
                }
            ]
        }
    elif isinstance(exception, UnsupportedMediaTypeError):
        error_response = {
            "detail": [
                {
                    "loc": ["headers", "content-type"],
                    "msg": str(exception),
                    "type": "unsupported_media_type",
                }
            ]
        }
    elif status_code >= 500:
        # Sanitize server errors — never leak internal details to the client
        error_response = json.loads(_SANITIZED_500_BODY)
    else:
        try:
            error_response = adapter.format_error(exception)
        except Exception:
            logger.exception("adapter.format_error raised an unexpected exception")
            return _sanitized_response()

    # Stamp the stability marker on every default envelope, but never mutate a
    # successful custom formatter's output — callers own that shape entirely.
    if not used_custom_formatter and isinstance(error_response, dict):
        error_response.setdefault("error_format_version", ERROR_FORMAT_VERSION)

    try:
        rich = isinstance(error_response, ErrorResponseSpec)
        if isinstance(error_response, ErrorResponseSpec):
            if not request_validation:
                raise ValueError("rich error responses require request-validation origin")
            content = error_response.content
        else:
            content = error_response
        if not isinstance(content, dict):
            raise TypeError("error formatter content must be a dictionary")
        fixed = validation_error_response if request_validation else None
        media_type = "application/json"
        if fixed is not None:
            response_status_code = fixed.status_code
            media_type = fixed.media_type
        headers = None
        if isinstance(error_response, ErrorResponseSpec):
            headers = error_response.headers
            if error_response.status_code is not None:
                selected_status = validation_status(error_response.status_code)
                if fixed is not None and selected_status != fixed.status_code:
                    raise ValueError("formatter status disagrees with fixed contract")
                response_status_code = selected_status
            if error_response.media_type is not None:
                selected_media = json_media_type(error_response.media_type)
                if fixed is not None and selected_media != fixed.media_type:
                    raise ValueError("formatter media type disagrees with fixed contract")
                media_type = selected_media
        if request_validation and error_type_adapter is not None:
            validated = error_type_adapter.validate_python(content)
            content = error_type_adapter.dump_python(validated, mode="json", by_alias=True)
        body = json.dumps(content, allow_nan=not (rich or fixed is not None))
        return build_response(body, response_status_code, media_type, headers)
    except Exception:
        logger.exception("error_response could not be serialized to JSON")
        return _sanitized_response()


def _sanitized_response() -> HttpResponse:
    return HttpResponse(
        body=_SANITIZED_500_BODY,
        status_code=500,
        headers={"Content-Type": "application/json"},
    )
