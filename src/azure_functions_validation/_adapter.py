"""Validation adapter layer for request/response validation."""

import json
from typing import Any, Protocol

from azure.functions import HttpRequest
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError


class ValidationAdapter(Protocol):
    """Protocol defining the interface for validation adapters."""

    def parse_body(self, req: HttpRequest, model: type[BaseModel]) -> Any:
        """Parse and validate request body.

        Args:
            req: Azure Functions HttpRequest
            model: Pydantic model class to validate against

        Returns:
            Validated model instance

        Raises:
            ValidationError: If body is missing or validation fails
            ValueError: If JSON parsing fails
        """
        ...

    def parse_query(self, req: HttpRequest, model: type[BaseModel]) -> Any:
        """Parse and validate query parameters.

        Args:
            req: The incoming Azure Functions HTTP request providing query parameters.
            model: The Pydantic model class to validate the query parameters against.

        Returns:
            An instance of ``model`` or another adapter-specific validated representation
            derived from the query parameters.

        Raises:
            Exception: If validation of the query parameters fails.
        """
        ...

    def parse_path(self, req: HttpRequest, model: type[BaseModel]) -> Any:
        """Parse and validate path parameters.

        Args:
            req: The incoming Azure Functions HTTP request providing route parameters.
            model: The Pydantic model class to validate the path parameters against.

        Returns:
            An instance of ``model`` or another adapter-specific validated representation
            derived from the path parameters.

        Raises:
            Exception: If validation of the path parameters fails.
        """
        ...

    def parse_headers(self, req: HttpRequest, model: type[BaseModel]) -> Any:
        """Parse and validate request headers.

        Args:
            req: The incoming Azure Functions HTTP request providing headers.
            model: The Pydantic model class to validate the headers against.

        Returns:
            An instance of ``model`` or another adapter-specific validated representation
            derived from the request headers.

        Raises:
            Exception: If validation of the headers fails.
        """
        ...

    def validate_response(self, obj: Any, model: type[BaseModel]) -> Any:
        """Validate response object against model.

        Args:
            obj: Response object (BaseModel instance or dict)
            model: Pydantic model class to validate against

        Returns:
            Validated model instance

        Raises:
            ValidationError: If validation fails
        """
        ...

    def serialize(self, obj: Any) -> tuple[str | bytes, str]:
        """Serialize response object to content and content-type.

        Args:
            obj: Object to serialize (BaseModel, dict, list, str, bytes)

        Returns:
            Tuple of (content, content_type)

        Raises:
            TypeError: If object type is not supported
        """
        ...

    def format_error(self, exc: Exception) -> dict[str, Any]:
        """Format exception into standardized error response.

        Args:
            exc: Exception to format

        Returns:
            Error response dict with 'detail' key
        """
        ...


class PydanticAdapter:
    """Concrete validation adapter implementation using Pydantic v2."""

    def parse_body(self, req: HttpRequest, model: type[BaseModel]) -> Any:
        """Parse and validate request body from JSON.

        Args:
            req: Azure Functions HttpRequest
            model: Pydantic model class to validate against

        Returns:
            Validated model instance

        Raises:
            PydanticValidationError: If body is missing (with type="missing")
            ValueError: If JSON is invalid (with "Invalid JSON" message)
        """
        body = req.get_body()

        # Handle empty body
        if not body:
            raise PydanticValidationError.from_exception_data(
                "ValidationError",
                [
                    {
                        "type": "missing",
                        "loc": ("body",),
                        "input": None,
                    }
                ],
            )

        # Parse JSON
        try:
            body_str = body.decode("utf-8")
            data = json.loads(body_str)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ValueError("Invalid JSON") from e

        # Validate with Pydantic
        return model.model_validate(data)

    def parse_query(self, req: HttpRequest, model: type[BaseModel]) -> Any:
        """Parse and validate query parameters.

        Args:
            req: Azure Functions HttpRequest providing query parameters
            model: Pydantic model class to validate against

        Returns:
            Validated model instance

        Raises:
            PydanticValidationError: If validation fails
        """
        return model.model_validate(req.params)

    def parse_path(self, req: HttpRequest, model: type[BaseModel]) -> Any:
        """Parse and validate path parameters.

        Args:
            req: Azure Functions HttpRequest providing route parameters
            model: Pydantic model class to validate against

        Returns:
            Validated model instance

        Raises:
            PydanticValidationError: If validation fails
        """
        return model.model_validate(req.route_params)

    def parse_headers(self, req: HttpRequest, model: type[BaseModel]) -> Any:
        """Parse and validate request headers.

        Args:
            req: Azure Functions HttpRequest providing headers
            model: Pydantic model class to validate against

        Returns:
            Validated model instance

        Raises:
            PydanticValidationError: If validation fails
        """
        return model.model_validate(dict(req.headers))

    def validate_response(self, obj: Any, model: type[BaseModel]) -> Any:
        """Validate response object.

        Args:
            obj: Response object (BaseModel instance or dict)
            model: Pydantic model class to validate against

        Returns:
            Validated model instance

        Raises:
            PydanticValidationError: If validation fails
            TypeError: If response type is invalid
        """
        if isinstance(obj, model):
            # Already a valid instance
            return obj
        elif isinstance(obj, dict):
            # Validate dict against model
            return model.model_validate(obj)
        else:
            # Invalid response type - raise TypeError
            raise TypeError(f"Expected {model.__name__} or dict, got {type(obj).__name__}")

    def serialize(self, obj: Any) -> tuple[str | bytes, str]:
        """Serialize response object.

        Args:
            obj: Object to serialize

        Returns:
            Tuple of (content, content_type)

        Raises:
            TypeError: If object type is not supported
        """
        content: str | bytes
        content_type: str

        if isinstance(obj, BaseModel):
            # Serialize Pydantic model to JSON
            content = obj.model_dump_json()
            content_type = "application/json"
        elif isinstance(obj, (dict, list)):
            # Serialize dict/list to JSON
            content = json.dumps(obj)
            content_type = "application/json"
        elif isinstance(obj, str):
            # Plain text
            content = obj
            content_type = "text/plain; charset=utf-8"
        elif isinstance(obj, bytes):
            # Binary data
            content = obj
            content_type = "application/octet-stream"
        else:
            raise TypeError(f"Cannot serialize type {type(obj).__name__}")

        return content, content_type

    def format_error(self, exc: Exception) -> dict[str, Any]:
        """Format exception into standardized error response.

        Args:
            exc: Exception to format (typically PydanticValidationError)

        Returns:
            Error response dict with 'detail' key containing list of errors
        """
        if isinstance(exc, PydanticValidationError):
            # Map Pydantic v2 errors to standardized types
            detail = []
            for error in exc.errors():
                error_type = self._map_error_type(error["type"])
                detail.append(
                    {
                        "loc": list(error["loc"]),
                        "msg": error["msg"],
                        "type": error_type,
                    }
                )
            return {"detail": detail}
        else:
            # Generic exception
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
        """Map Pydantic v2 error types to standardized types.

        Args:
            pydantic_type: Pydantic error type string

        Returns:
            Standardized error type string
        """
        # Direct mappings for standard types
        if pydantic_type in ("missing", "missing_required"):
            return "missing"
        elif pydantic_type == "string_too_short":
            return "string_too_short"
        elif pydantic_type == "string_too_long":
            return "string_too_long"
        elif pydantic_type in ("greater_than", "greater_than_equal", "too_large"):
            return "number_too_large"
        elif pydantic_type in ("less_than", "less_than_equal", "too_small"):
            return "number_too_small"
        # Pattern-based mappings
        elif pydantic_type.startswith("type_error"):
            return "invalid_type"
        elif pydantic_type.startswith("value_error"):
            return "value_error"
        # Default mapping for unknown types
        else:
            return "value_error"
