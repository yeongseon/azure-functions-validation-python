"""azure-functions-validation package."""

from .contract import contract_test, verify_contracts
from .decorator import ErrorFormatter, validate_http
from .exceptions import ResponseValidationError
from .metadata import (
    describe_validation_contract,
    get_contract_schema,
    get_request_contract_metadata,
    get_response_contract_metadata,
    get_validation_error_contract,
)
from .openapi import generate_422_error_schema, get_validation_error_examples
from .registry import clear_global_error_handlers, register_global_error_handler

__all__ = [
    "__version__",
    "validate_http",
    "ResponseValidationError",
    "ErrorFormatter",
    "register_global_error_handler",
    "clear_global_error_handlers",
    "get_contract_schema",
    "get_request_contract_metadata",
    "get_response_contract_metadata",
    "get_validation_error_contract",
    "describe_validation_contract",
    "generate_422_error_schema",
    "get_validation_error_examples",
    "contract_test",
    "verify_contracts",
]

__version__ = "0.3.0"
