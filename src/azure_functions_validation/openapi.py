"""OpenAPI integration utilities for azure-functions-openapi."""

from typing import Any, Dict, List, Type, cast

from pydantic import BaseModel

from .metadata import get_validation_error_contract


def generate_422_error_schema(request_model: Type[BaseModel]) -> Dict[str, Any]:
    """Generate OpenAPI schema for 422 validation error responses.

    Args:
        request_model: Pydantic model class for request validation

    Returns:
        OpenAPI schema dict for 422 error response
    """
    error_contract = get_validation_error_contract(request_model)
    if error_contract is None:
        raise ValueError("request_model is required to generate a 422 error schema")
    return cast(Dict[str, Any], error_contract["schema"])


def get_validation_error_examples(request_model: Type[BaseModel]) -> List[Dict[str, Any]]:
    """Generate example 422 error responses.

    Generates examples for common validation failure modes including missing
    required fields and constraint violations (string length, numeric range,
    pattern mismatch).

    Args:
        request_model: Pydantic model class for request validation

    Returns:
        List of example 422 error responses
    """
    error_contract = get_validation_error_contract(request_model)
    if error_contract is None:
        raise ValueError("request_model is required to generate 422 error examples")
    return cast(List[Dict[str, Any]], error_contract["examples"])
