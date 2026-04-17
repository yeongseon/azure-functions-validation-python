"""Error types and formatting for azure-functions-validation-python."""

from __future__ import annotations

import json
from typing import Any, Callable

from azure.functions import HttpResponse

from .adapter import ValidationAdapter

ErrorFormatter = Callable[[Exception, int], dict[str, Any]]


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


def format_error_response(
    exception: Exception,
    status_code: int,
    adapter: ValidationAdapter,
    error_formatter: ErrorFormatter | None = None,
) -> HttpResponse:
    """Build an ``HttpResponse`` for a validation or parsing error.

    Args:
        exception: The caught exception.
        status_code: HTTP status code for the response.
        adapter: The validation adapter used for default formatting.
        error_formatter: Optional per-handler custom formatter.

    Returns:
        An ``HttpResponse`` with a JSON error body.
    """
    if error_formatter is not None:
        error_response = error_formatter(exception, status_code)
    elif status_code >= 500:
        # Sanitize server errors — never leak internal details to the client
        error_response = {
            "detail": [
                {
                    "loc": [],
                    "msg": "Internal Server Error",
                    "type": "server_error",
                }
            ]
        }
    else:
        error_response = adapter.format_error(exception)

    return HttpResponse(
        body=json.dumps(error_response),
        status_code=status_code,
        headers={"Content-Type": "application/json"},
    )
