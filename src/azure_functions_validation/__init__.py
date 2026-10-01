"""azure-functions-validation package."""

import sys
import warnings

from .adapter import PydanticAdapter, ValidationAdapter
from .decorator import validate_http
from .errors import ErrorFormatter, HttpError, ResponseValidationError, SerializationError

__all__ = [
    "__version__",
    "validate_http",
    "ResponseValidationError",
    "SerializationError",
    "ErrorFormatter",
    "ValidationAdapter",
    "PydanticAdapter",
    "HttpError",
]

__version__ = "0.12.0"


if sys.version_info < (3, 11):
    warnings.warn(
        "azure-functions-validation will drop support for Python 3.10 in its next minor release. "
        "Python 3.10 reaches end of life in October 2026; upgrade to Python 3.11 "
        "or newer to keep receiving updates.",
        FutureWarning,
        stacklevel=2,
    )
