"""azure-functions-validation package."""

from .adapter import PydanticAdapter, ValidationAdapter
from .decorator import validate_http
from .errors import (
    AdapterValidationError,
    AggregatedValidationError,
    ErrorFormatter,
    HttpError,
    InternalServerError,
    MalformedRequestError,
    PayloadTooLargeError,
    ResponseValidationError,
    SerializationError,
    UnsupportedMediaTypeError,
)
from .testing import AdapterConformanceTests

__all__ = [
    "__version__",
    "validate_http",
    "ResponseValidationError",
    "SerializationError",
    "ErrorFormatter",
    "ValidationAdapter",
    "PydanticAdapter",
    "HttpError",
    "InternalServerError",
    "MalformedRequestError",
    "PayloadTooLargeError",
    "UnsupportedMediaTypeError",
    "AdapterValidationError",
    "AggregatedValidationError",
    "AdapterConformanceTests",
]

__version__ = "0.16.0"
