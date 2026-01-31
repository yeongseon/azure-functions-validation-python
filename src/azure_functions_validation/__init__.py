"""azure-functions-validation package."""

from .decorator import ErrorFormatter, validate_http
from .exceptions import ResponseValidationError
from .registry import clear_global_error_handlers, register_global_error_handler

__all__ = [
    "__version__",
    "validate_http",
    "ResponseValidationError",
    "ErrorFormatter",
    "register_global_error_handler",
    "clear_global_error_handlers",
]

__version__ = "0.2.0"
