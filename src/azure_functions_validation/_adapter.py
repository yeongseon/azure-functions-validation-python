"""Validation adapter interface and Pydantic implementation."""

import json
from typing import Any, Protocol

from azure.functions import HttpRequest
from pydantic import BaseModel, ValidationError


class ValidationAdapter(Protocol):
    """Protocol for validation adapters."""

    def parse_body(self, req: HttpRequest, model: type[BaseModel]) -> Any:
        """Parse and validate request body."""
        ...

    def validate_response(self, obj: Any, model: type[BaseModel]) -> Any:
        """Validate response object."""
        ...

    def serialize(self, obj: Any) -> tuple[str | bytes, str]:
        """Serialize object to response content and content type."""
        ...

    def format_error(self, exc: Exception) -> dict[str, Any]:
        """Format validation error into standard error response."""
        ...


class PydanticAdapter:
    """Pydantic v2 validation adapter."""

    def parse_body(self, req: HttpRequest, model: type[BaseModel]) -> Any:
        """Parse and validate request body using Pydantic."""
        body_bytes = req.get_body()
        if not body_bytes:
            raise ValidationError.from_exception_data(
                "validation_error",
                [
                    {
                        "type": "missing",
                        "loc": ("body",),
                        "input": None,
                    }
                ],
            )
        try:
            return model.model_validate_json(body_bytes)
        except ValidationError as e:
            # Check if this is a JSON parsing error (not a validation error)
            errors = e.errors()
            if len(errors) == 1 and errors[0].get("type") in ("json_invalid", "json_type"):
                # This is a JSON parsing error, not a validation error
                raise ValueError("Invalid JSON") from e
            # Re-raise ValidationError for actual validation errors
            raise
        except (ValueError, TypeError) as e:
            # JSON parsing error (not ValidationError)
            raise ValueError("Invalid JSON") from e

    def validate_response(self, obj: Any, model: type[BaseModel]) -> Any:
        """Validate response object using Pydantic."""
        if isinstance(obj, model):
            return obj
        if isinstance(obj, dict):
            return model.model_validate(obj)
        raise TypeError(f"Cannot validate response of type {type(obj)}")

    def serialize(self, obj: Any) -> tuple[str | bytes, str]:
        """Serialize object to response content and content type."""
        if isinstance(obj, BaseModel):
            return obj.model_dump_json(), "application/json"
        if isinstance(obj, (dict, list)):
            return json.dumps(obj), "application/json"
        if isinstance(obj, str):
            return obj, "text/plain; charset=utf-8"
        if isinstance(obj, bytes):
            return obj, "application/octet-stream"
        raise TypeError(f"Cannot serialize type {type(obj)}")

    def format_error(self, exc: Exception) -> dict[str, Any]:
        """Format validation error into standard error response."""
        if isinstance(exc, ValidationError):
            return self._format_pydantic_error(exc)
        return {"detail": [{"loc": ["body"], "msg": str(exc), "type": "value_error"}]}

    def _format_pydantic_error(self, exc: ValidationError) -> dict[str, Any]:
        """Format Pydantic ValidationError into standard error response."""
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

    def _map_error_type(self, pydantic_type: str) -> str:
        """Map Pydantic v2 error types to standard error types."""
        # Map Pydantic error types to standard types defined in PRD
        type_mapping = {
            "missing": "missing",
            "missing_required": "missing",
            "string_too_short": "string_too_short",
            "string_too_long": "string_too_long",
            "greater_than": "number_too_large",
            "greater_than_equal": "number_too_large",
            "too_large": "number_too_large",
            "less_than": "number_too_small",
            "less_than_equal": "number_too_small",
            "too_small": "number_too_small",
        }

        # Check for prefixes
        if pydantic_type.startswith("type_error"):
            return "invalid_type"
        if pydantic_type.startswith("value_error"):
            return "value_error"

        # Direct mapping
        return type_mapping.get(pydantic_type, "value_error")
