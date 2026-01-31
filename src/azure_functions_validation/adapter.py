"""Validation adapter layer for request/response validation."""

import json
from typing import Any, Protocol, Tuple, Union, get_args, get_origin

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
            req: Azure Functions HttpRequest
            model: Pydantic model class to validate against

        Returns:
            Validated model instance

        Raises:
            ValidationError: If validation fails
        """
        ...

    def parse_path(self, req: HttpRequest, model: type[BaseModel]) -> Any:
        """Parse and validate path parameters.

        Args:
            req: Azure Functions HttpRequest
            model: Pydantic model class to validate against

        Returns:
            Validated model instance

        Raises:
            ValidationError: If validation fails
        """
        ...

    def parse_headers(self, req: HttpRequest, model: type[BaseModel]) -> Any:
        """Parse and validate headers.

        Args:
            req: Azure Functions HttpRequest
            model: Pydantic model class to validate against

        Returns:
            Validated model instance

        Raises:
            ValidationError: If validation fails
        """
        ...

    def validate_response(self, obj: Any, model: type[BaseModel]) -> Any:
        """Validate response object against model.

        Args:
            obj: Response object (BaseModel instance, dict, list, etc.)
            model: Pydantic model class to validate against

        Returns:
            Validated model instance

        Raises:
            ValidationError: If validation fails
            TypeError: If response type is invalid
        """
        ...

    def serialize(self, obj: Any) -> Tuple[Union[str, bytes], str]:
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
        body_str = body.decode("utf-8")
        if not body_str.strip():
            # Empty JSON string - this is a missing body, not invalid JSON
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

        try:
            data = json.loads(body_str)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ValueError("Invalid JSON") from e

        # Validate with Pydantic
        return model.model_validate(data)

    def parse_query(self, req: HttpRequest, model: type[BaseModel]) -> Any:
        """Parse and validate query parameters.

        Args:
            req: Azure Functions HttpRequest
            model: Pydantic model class to validate against

        Returns:
            Validated model instance

        Raises:
            PydanticValidationError: If validation fails
        """
        # Parse query parameters
        query_params = req.params or {}

        # Convert MultiDict to regular dict
        query_data = {}
        for key, value in query_params.items():
            if isinstance(value, list):
                query_data[key] = value[0] if len(value) == 1 else value
            else:
                query_data[key] = value

        # Validate with Pydantic
        return model.model_validate(query_data)

    def parse_path(self, req: HttpRequest, model: type[BaseModel]) -> Any:
        """Parse and validate path parameters.

        Args:
            req: Azure Functions HttpRequest
            model: Pydantic model class to validate against

        Returns:
            Validated model instance

        Raises:
            PydanticValidationError: If validation fails
        """
        # Parse route parameters
        route_params = req.route_params or {}

        # Validate with Pydantic
        return model.model_validate(route_params)

    def parse_headers(self, req: HttpRequest, model: type[BaseModel]) -> Any:
        """Parse and validate headers.

        Args:
            req: Azure Functions HttpRequest
            model: Pydantic model class to validate against

        Returns:
            Validated model instance

        Raises:
            PydanticValidationError: If validation fails
        """
        # Parse headers
        headers = req.headers or {}

        # Convert to regular dict and handle multi-value headers
        header_data = {}
        for key, value in headers.items():
            if isinstance(value, list):
                header_data[key] = value[0] if len(value) == 1 else value
            else:
                header_data[key] = value

        # Validate with Pydantic
        return model.model_validate(header_data)

    def validate_response(self, obj: Any, model: type[BaseModel]) -> Any:
        """Validate response object against model.

        Args:
            obj: Response object (BaseModel instance, dict, list, etc.)
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
        elif isinstance(obj, list):
            # Validate list against model (for List[model] types)
            model_origin = get_origin(model)
            model_args = get_args(model)

            if model_origin is list:
                # This is a List[Model] type
                if model_args:
                    item_model = model_args[0]
                    return [item_model.model_validate(item) for item in obj]
                else:
                    # Plain list, just return as-is
                    return obj
            else:
                # Model is not a list type, but we have a list - validate each item
                return [model.model_validate(item) for item in obj]
        else:
            # Invalid response type - raise TypeError
            raise TypeError(f"Expected {model.__name__}, dict, or list, got {type(obj).__name__}")

    def serialize(self, obj: Any) -> Tuple[Union[str, bytes], str]:
        """Serialize response object to content and content-type.

        Args:
            obj: Object to serialize (BaseModel, dict, list, str, bytes)

        Returns:
            Tuple of (content, content_type)

        Raises:
            TypeError: If object type is not supported
        """
        content: Union[str, bytes]
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
