"""OpenAPI integration utilities for azure-functions-openapi."""

from typing import Any, Dict, List, Type, cast

from pydantic import BaseModel

from .metadata import (
    get_contract_schema,
    get_validation_error_contract,
)


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


def get_openapi_response_metadata(
    *,
    body: Type[BaseModel] | None = None,
    query: Type[BaseModel] | None = None,
    path: Type[BaseModel] | None = None,
    headers: Type[BaseModel] | None = None,
    request_model: Type[BaseModel] | None = None,
    response_model: Type[BaseModel] | None = None,
) -> Dict[str, Dict[str, Any]]:
    """Generate ``@openapi``-compatible response metadata from validation models.

    Returns a ``response`` dict keyed by HTTP status code that can be passed
    directly to ``@openapi(response=...)`` in ``azure-functions-openapi``.

    The result always includes:

    * **200** – derived from *response_model* when provided.
    * **422** – derived from all validated request sources (body, query, path,
      headers) with schema and examples.

    Example::

        from azure_functions_validation.openapi import get_openapi_response_metadata

        responses = get_openapi_response_metadata(
            body=CreateUserRequest,
            response_model=CreateUserResponse,
        )
        # Pass directly to @openapi(response=responses)

    Args:
        body: Pydantic model for request body validation.
        query: Pydantic model for query parameter validation.
        path: Pydantic model for path parameter validation.
        headers: Pydantic model for header validation.
        request_model: Alias for *body* (cannot be used together with *body*).
        response_model: Pydantic model for response validation.

    Returns:
        Dict keyed by status code with OpenAPI response objects.
    """
    if request_model is not None and body is not None:
        raise ValueError("Cannot use request_model together with body")

    effective_body = request_model or body
    responses: Dict[str, Dict[str, Any]] = {}

    # 200 response from response_model
    if response_model is not None:
        responses["200"] = {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "schema": get_contract_schema(response_model),
                }
            },
        }

    # 422 response from all validated sources
    error_contract = get_validation_error_contract(
        effective_body,
        query=query,
        path=path,
        headers=headers,
    )
    if error_contract is not None:
        responses["422"] = {
            "description": "Validation Error",
            "content": {
                "application/json": {
                    "schema": error_contract["schema"],
                    "examples": {
                        example["summary"]: {
                            "summary": example["summary"],
                            "value": example["value"],
                        }
                        for example in error_contract["examples"]
                    },
                }
            },
        }

    return responses
