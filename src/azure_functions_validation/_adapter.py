"""Validation adapter for request/response validation using Pydantic v2."""

from typing import Any, Protocol

from azure.functions import HttpRequest
from pydantic import BaseModel, ValidationError
from pydantic_core import InitErrorDetails


class ValidationAdapter(Protocol):
    """Protocol defining the interface for validation adapters."""

    def parse_body(self, req: HttpRequest, model: type[BaseModel]) -> Any:
        """Parse and validate request body.

        Args:
            req: The HTTP request object
            model: The Pydantic model to validate against

        Returns:
            Validated model instance

        Raises:
            ValidationError: If validation fails
            ValueError: If JSON is invalid
        """
        ...

    def validate_response(self, obj: Any, model: type[BaseModel]) -> Any:
        """Validate response object against model.

        Args:
            obj: The object to validate
            model: The Pydantic model to validate against

        Returns:
            Validated model instance

        Raises:
            ValidationError: If validation fails
        """
        ...

    def serialize(self, obj: Any) -> tuple[str | bytes, str]:
        """Serialize object to appropriate format.

        Args:
            obj: The object to serialize

        Returns:
            Tuple of (content, content_type)

        Raises:
            TypeError: If object type is not supported
        """
        ...

    def format_error(self, exc: Exception) -> dict[str, Any]:
        """Format exception into standardized error response.

        Args:
            exc: The exception to format

        Returns:
            Standardized error dictionary
        """
        ...


class PydanticAdapter:
    """Concrete implementation of validation adapter using Pydantic v2."""

    def parse_body(self, req: HttpRequest, model: type[BaseModel]) -> Any:
        """Parse and validate request body from JSON.

        Args:
            req: The HTTP request object
            model: The Pydantic model to validate against

        Returns:
            Validated model instance

        Raises:
            ValidationError: If body is empty (with type="missing")
            ValueError: If JSON is invalid (with "Invalid JSON" message)
        """
        body = req.get_body()

        # Handle empty body
        if not body:
            # Create a ValidationError with type="missing"
            error_details: InitErrorDetails = {
                "type": "missing",
                "loc": ("body",),
                "input": None,
            }
            raise ValidationError.from_exception_data(
                "ValidationError",
                [error_details],
            )

        # Try to parse JSON
        try:
            data = req.get_json()
        except Exception:
            raise ValueError("Invalid JSON")

        # Validate against model
        return model.model_validate(data)

    def validate_response(self, obj: Any, model: type[BaseModel]) -> Any:
        """Validate response object against model.

        Args:
            obj: The object to validate (BaseModel instance or dict)
            model: The Pydantic model to validate against

        Returns:
            Validated model instance

        Raises:
            ValidationError: If validation fails
            TypeError: If object type is not BaseModel or dict
        """
        if isinstance(obj, BaseModel):
            # If already a BaseModel instance, validate it matches the expected model
            return model.model_validate(obj.model_dump())
        elif isinstance(obj, dict):
            # Validate dict against model
            return model.model_validate(obj)
        else:
            raise TypeError(f"Expected BaseModel or dict, got {type(obj).__name__}")

    def serialize(self, obj: Any) -> tuple[str | bytes, str]:
        """Serialize object to appropriate format.

        Args:
            obj: The object to serialize

        Returns:
            Tuple of (content, content_type)

        Raises:
            TypeError: If object type is not supported
        """
        if isinstance(obj, BaseModel):
            # Serialize BaseModel to JSON
            return obj.model_dump_json(), "application/json"
        elif isinstance(obj, (dict, list)):
            # Serialize dict/list to JSON
            import json

            return json.dumps(obj), "application/json"
        elif isinstance(obj, str):
            # Return string as-is with text/plain content type
            return obj, "text/plain; charset=utf-8"
        elif isinstance(obj, bytes):
            # Return bytes as-is with binary content type
            return obj, "application/octet-stream"
        else:
            raise TypeError(f"Cannot serialize type {type(obj).__name__}")

    def format_error(self, exc: Exception) -> dict[str, Any]:
        """Format exception into standardized error response.

        Maps Pydantic v2 error types to standard types according to PRD.

        Args:
            exc: The exception to format

        Returns:
            Standardized error dictionary with "detail" list
        """
        if isinstance(exc, ValidationError):
            errors = []
            for error in exc.errors():
                error_type = self._map_error_type(error.get("type", "value_error"))
                errors.append(
                    {
                        "loc": list(error.get("loc", ())),
                        "msg": error.get("msg", "Validation error"),
                        "type": error_type,
                    }
                )
            return {"detail": errors}
        else:
            # Generic exception formatting
            return {
                "detail": [
                    {
                        "loc": ["body"],
                        "msg": str(exc),
                        "type": "value_error",
                    }
                ]
            }

    def _map_error_type(self, pydantic_type: str) -> str:
        """Map Pydantic v2 error types to standard types.

        Args:
            pydantic_type: The Pydantic error type

        Returns:
            Mapped standard error type
        """
        # Map missing types
        if pydantic_type in ("missing", "missing_required"):
            return "missing"

        # Keep string validation types
        if pydantic_type in ("string_too_short", "string_too_long"):
            return pydantic_type

        # Map number validation types - too large
        # Note: Pydantic v2 uses less_than_equal for upper bound violations
        if pydantic_type in ("greater_than", "less_than_equal", "too_large"):
            return "number_too_large"

        # Map number validation types - too small
        # Note: Pydantic v2 uses greater_than_equal for lower bound violations
        if pydantic_type in ("less_than", "greater_than_equal", "too_small"):
            return "number_too_small"

        # Map type errors (including int_parsing, float_parsing, etc.)
        if pydantic_type.startswith("type_error") or pydantic_type.endswith("_parsing"):
            return "invalid_type"

        # Map value errors
        if pydantic_type.startswith("value_error"):
            return "value_error"

        # Default to value_error for unmapped types
        return "value_error"
