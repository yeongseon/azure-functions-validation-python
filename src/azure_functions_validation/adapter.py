"""Validation adapter layer for request/response validation."""

import dataclasses
import json
from typing import Any, Protocol

from azure.functions import HttpRequest
from pydantic import BaseModel, TypeAdapter
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

    def validate_response(self, obj: Any, model: Any) -> Any:
        """Validate response object against model.

        Args:
            obj: Response object (BaseModel instance, dict, list, etc.)
            model: Pydantic model class or generic type (e.g. list[SomeModel]) to validate against

        Returns:
            Validated model instance

        Raises:
            PydanticValidationError: If validation fails
        """
        ...

    def serialize(self, obj: Any) -> tuple[str | bytes, str]:
        """Serialize response object to content and content-type.

        Args:
            obj: Object to serialize

        Returns:
            Tuple of (content, content_type)

        Raises:
            SerializationError: If object type is not supported
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
        except UnicodeDecodeError as e:
            raise ValueError("Invalid JSON") from e

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
        except json.JSONDecodeError as e:
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
            header_data[key] = value

        # Validate with Pydantic
        return model.model_validate(header_data)

    def validate_response(self, obj: Any, model: Any) -> Any:
        """Validate response object against model.

        Uses ``TypeAdapter`` to support both concrete ``BaseModel`` subclasses
        and parameterized generic types such as ``list[SomeModel]``.

        Args:
            obj: Response object (BaseModel instance, dict, list, etc.)
            model: Pydantic model class or generic type (e.g. list[SomeModel]) to validate against

        Returns:
            Validated model instance

        Raises:
            PydanticValidationError: If validation fails
        """
        ta = TypeAdapter(model)
        return ta.validate_python(obj)

    def serialize(self, obj: Any) -> tuple[str | bytes, str]:
        """Serialize response object to content and content-type.

        Args:
            obj: Object to serialize.
                Supported: BaseModel, dict, list, str,
                bytes, int, float, bool, dataclass.

        Returns:
            Tuple of (content, content_type)

        Raises:
            SerializationError: If object type is not supported
        """
        from .errors import SerializationError

        content: str | bytes
        content_type: str

        if isinstance(obj, BaseModel):
            # Serialize Pydantic model to JSON
            content = obj.model_dump_json()
            content_type = "application/json"
        elif isinstance(obj, (dict, list)):
            # Serialize dict/list to JSON, handling nested BaseModel instances
            def _default_serializer(value: Any) -> Any:
                if isinstance(value, BaseModel):
                    return value.model_dump(mode="json")
                if dataclasses.is_dataclass(value) and not isinstance(value, type):
                    return dataclasses.asdict(value)
                raise SerializationError(type(value).__name__)

            content = json.dumps(obj, default=_default_serializer)
            content_type = "application/json"
        elif isinstance(obj, str):
            # Plain text
            content = obj
            content_type = "text/plain; charset=utf-8"
        elif isinstance(obj, bytes):
            # Binary data
            content = obj
            content_type = "application/octet-stream"
        elif isinstance(obj, (int, float, bool)):
            # Scalar types — JSON-serialize
            content = json.dumps(obj)
            content_type = "application/json"
        elif dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            # Dataclass — serialize via dataclasses.asdict
            content = json.dumps(dataclasses.asdict(obj))
            content_type = "application/json"
        else:
            raise SerializationError(type(obj).__name__)

        return content, content_type

    def format_error(self, exc: Exception) -> dict[str, Any]:
        """Format exception into standardized error response.

        Args:
            exc: Exception to format (typically PydanticValidationError)

        Returns:
            Error response dict with 'detail' key containing list of errors
        """
        if isinstance(exc, PydanticValidationError):
            detail = []
            for error in exc.errors():
                detail.append(
                    {
                        "loc": list(error["loc"]),
                        "msg": error["msg"],
                        "type": error["type"],
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
