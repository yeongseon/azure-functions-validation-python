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
    from pydantic import TypeAdapter

    adapter = TypeAdapter(request_model)
    adapter.json_schema()

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

    Args:
        request_model: Pydantic model class for request validation

    Returns:
        List of example 422 error responses
    """
    examples: List[Dict[str, Any]] = []

    from pydantic import TypeAdapter

    adapter = TypeAdapter(request_model)

    if "properties" in adapter.json_schema():
        for field_name in adapter.json_schema()["properties"].keys():
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

    return examples
