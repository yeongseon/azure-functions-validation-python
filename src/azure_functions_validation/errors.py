"""Error types and formatting for azure-functions-validation."""

from __future__ import annotations

import json
from typing import Any, Callable, Optional

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


def format_error_response(
    exception: Exception,
    status_code: int,
    adapter: ValidationAdapter,
    error_formatter: Optional[ErrorFormatter] = None,
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
    else:
        error_response = adapter.format_error(exception)

    return HttpResponse(
        body=json.dumps(error_response),
        status_code=status_code,
        headers={"Content-Type": "application/json"},
    )
