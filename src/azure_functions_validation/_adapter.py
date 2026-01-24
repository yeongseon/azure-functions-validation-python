"""Pydantic adapter for request/response validation."""

import json
from typing import Any, Optional

from azure.functions import HttpRequest
from pydantic import BaseModel, ValidationError

from ._exceptions import ResponseValidationError


class PydanticAdapter:
    """Adapter for Pydantic-based validation and serialization."""

    def parse_body(self, req: HttpRequest, model: type[BaseModel]) -> BaseModel:
        """Parse and validate request body.

        Args:
            req: Azure Functions HttpRequest
            model: Pydantic model class to validate against

        Returns:
            Validated model instance

        Raises:
            ValueError: If JSON is invalid
            ValidationError: If validation fails
        """
        body_bytes = req.get_body()

        # Check if body is empty
        if not body_bytes:
            # Empty body - try to validate with empty dict
            try:
                return model.model_validate({})
            except ValidationError:
                # Re-raise as validation error (422)
                raise

        # Try to parse JSON
        try:
            body_dict = json.loads(body_bytes)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ValueError(f"Invalid JSON: {str(e)}")

        # Validate using Pydantic
        return model.model_validate(body_dict)

    def validate_response(self, obj: Any, model: type[BaseModel]) -> BaseModel:
        """Validate response object against model.

        Args:
            obj: Object to validate (can be dict, model instance, etc.)
            model: Pydantic model class to validate against

        Returns:
            Validated model instance

        Raises:
            ResponseValidationError: If validation fails
        """
        try:
            if isinstance(obj, BaseModel):
                # If it's already a model instance, validate it
                return model.model_validate(obj.model_dump())
            elif isinstance(obj, dict):
                # If it's a dict, validate directly
                return model.model_validate(obj)
            else:
                # Try to validate other types
                return model.model_validate(obj)
        except ValidationError as e:
            raise ResponseValidationError(f"Response validation failed: {str(e)}")

    def serialize(self, obj: Any, model: Optional[type[BaseModel]] = None) -> tuple[str, str]:
        """Serialize object to JSON.

        Args:
            obj: Object to serialize
            model: Optional model for validation

        Returns:
            Tuple of (content, content_type)
        """
        if isinstance(obj, BaseModel):
            # Serialize Pydantic model
            content = obj.model_dump_json()
            return content, "application/json"
        elif isinstance(obj, (dict, list)):
            # Serialize dict/list to JSON
            content = json.dumps(obj)
            return content, "application/json"
        elif isinstance(obj, str):
            # Return string as-is
            return obj, "text/plain; charset=utf-8"
        elif isinstance(obj, bytes):
            # Return bytes as-is
            return obj.decode("utf-8"), "application/octet-stream"
        else:
            # Try JSON serialization
            content = json.dumps(obj)
            return content, "application/json"

    def format_error(self, exc: Exception) -> dict[str, Any]:
        """Format exception as error response.

        Args:
            exc: Exception to format

        Returns:
            Error response dict with 'detail' field
        """
        if isinstance(exc, ValidationError):
            # Format Pydantic validation errors
            errors = []
            for error in exc.errors():
                error_type = self._map_error_type(error.get("type", "value_error"))
                errors.append(
                    {
                        "loc": list(error.get("loc", [])),
                        "msg": error.get("msg", "Validation error"),
                        "type": error_type,
                    }
                )
            return {"detail": errors}
        elif isinstance(exc, ValueError):
            # Format JSON parsing errors
            return {
                "detail": [
                    {
                        "loc": ["body"],
                        "msg": "Invalid JSON",
                        "type": "json_invalid",
                    }
                ]
            }
        elif isinstance(exc, ResponseValidationError):
            # Format response validation errors
            return {
                "detail": [
                    {
                        "loc": ["response"],
                        "msg": "Response validation error",
                        "type": "response_validation_error",
                    }
                ]
            }
        else:
            # Generic error
            return {
                "detail": [
                    {
                        "loc": [],
                        "msg": str(exc),
                        "type": "value_error",
                    }
                ]
            }

    def _map_error_type(self, pydantic_type: str) -> str:
        """Map Pydantic error types to standard types.

        Args:
            pydantic_type: Pydantic error type

        Returns:
            Standardized error type
        """
        # Map common Pydantic v2 error types to our standard types
        type_mapping = {
            "missing": "missing",
            "missing_required": "missing",
            "string_too_short": "string_too_short",
            "string_too_long": "string_too_long",
            "greater_than": "number_too_large",
            "greater_than_equal": "number_too_large",
            "less_than": "number_too_small",
            "less_than_equal": "number_too_small",
            "too_large": "number_too_large",
            "too_small": "number_too_small",
        }

        # Check for prefixes
        if pydantic_type.startswith("type_error"):
            return "invalid_type"
        elif pydantic_type.startswith("value_error"):
            return "value_error"

        # Return mapped type or default to value_error
        return type_mapping.get(pydantic_type, "value_error")
