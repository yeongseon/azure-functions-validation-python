"""OpenAPI integration utilities for azure-functions-openapi."""

from typing import Any, Dict, List, Type

from pydantic import BaseModel


def generate_422_error_schema(request_model: Type[BaseModel]) -> Dict[str, Any]:
    """Generate OpenAPI schema for 422 validation error responses.

    Args:
        request_model: Pydantic model class for request validation

    Returns:
        OpenAPI schema dict for 422 error response
    """
    return {
        "type": "object",
        "properties": {
            "detail": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "loc": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Location of error",
                        },
                        "msg": {
                            "type": "string",
                            "description": "Error message",
                        },
                        "type": {
                            "type": "string",
                            "description": "Error type identifier",
                        },
                    },
                },
            }
        },
    }


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
    from pydantic import TypeAdapter

    examples: List[Dict[str, Any]] = []
    adapter = TypeAdapter(request_model)
    schema = adapter.json_schema()

    properties = schema.get("properties", {})
    required_fields = set(schema.get("required", []))

    for field_name, field_schema in properties.items():
        # Missing required field example
        if field_name in required_fields:
            examples.append(
                {
                    "summary": f"Missing required field: {field_name}",
                    "value": {
                        "detail": [
                            {
                                "loc": ["body", field_name],
                                "msg": "Field required",
                                "type": "missing",
                            }
                        ]
                    },
                }
            )

        # String constraint violations
        if field_schema.get("type") == "string":
            if "minLength" in field_schema:
                examples.append(
                    {
                        "summary": f"String too short: {field_name}",
                        "value": {
                            "detail": [
                                {
                                    "loc": ["body", field_name],
                                    "msg": f"String should have at least {field_schema['minLength']} character(s)",
                                    "type": "string_too_short",
                                }
                            ]
                        },
                    }
                )
            if "pattern" in field_schema:
                examples.append(
                    {
                        "summary": f"Pattern mismatch: {field_name}",
                        "value": {
                            "detail": [
                                {
                                    "loc": ["body", field_name],
                                    "msg": f"String should match pattern '{field_schema['pattern']}'",
                                    "type": "string_pattern_mismatch",
                                }
                            ]
                        },
                    }
                )

        # Numeric constraint violations
        if field_schema.get("type") == "integer" or field_schema.get("type") == "number":
            if "minimum" in field_schema or "exclusiveMinimum" in field_schema:
                examples.append(
                    {
                        "summary": f"Value too small: {field_name}",
                        "value": {
                            "detail": [
                                {
                                    "loc": ["body", field_name],
                                    "msg": "Value is too small",
                                    "type": "too_small",
                                }
                            ]
                        },
                    }
                )
            if "maximum" in field_schema or "exclusiveMaximum" in field_schema:
                examples.append(
                    {
                        "summary": f"Value too large: {field_name}",
                        "value": {
                            "detail": [
                                {
                                    "loc": ["body", field_name],
                                    "msg": "Value is too large",
                                    "type": "too_large",
                                }
                            ]
                        },
                    }
                )

    return examples
