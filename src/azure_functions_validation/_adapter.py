"""Validation adapter layer for request/response validation."""

import json
from typing import Any, Protocol, Type

from azure.functions import HttpRequest
from pydantic import BaseModel, TypeAdapter
from pydantic import ValidationError as PydanticValidationError


class ValidationAdapter(Protocol):
    """Protocol defining the interface for validation adapters."""

    def parse_body(self, req: HttpRequest, model: type[BaseModel]) -> Any: ...
    def parse_query(self, req: HttpRequest, model: Type[BaseModel]) -> Any: ...
    def parse_path(self, req: HttpRequest, model: Type[BaseModel]) -> Any: ...
    def parse_headers(self, req: HttpRequest, model: Type[BaseModel]) -> Any: ...
    def validate_response(self, obj: Any, model: type[BaseModel]) -> Any: ...
    def serialize(self, obj: Any) -> tuple[str | bytes, str]: ...
    def format_error(self, exc: Exception) -> dict[str, Any]: ...


class PydanticAdapter:
    """Concrete validation adapter implementation using Pydantic v2."""

    def parse_body(self, req: HttpRequest, model: type[BaseModel]) -> Any:
        body = req.get_body()
        if not body:
            raise PydanticValidationError.from_exception_data(
                "Missing Body", [{"type": "missing", "loc": ("body",), "input": None}]
            )
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ValueError("Invalid JSON in body") from e
        return TypeAdapter(model).validate_python(data)

    def parse_query(self, req: HttpRequest, model: Type[BaseModel]) -> Any:
        """Parse and validate query parameters."""
        return TypeAdapter(model).validate_python(req.params)

    def parse_path(self, req: HttpRequest, model: Type[BaseModel]) -> Any:
        """Parse and validate path parameters."""
        return TypeAdapter(model).validate_python(req.route_params)

    def parse_headers(self, req: HttpRequest, model: Type[BaseModel]) -> Any:
        """Parse and validate request headers."""
        return TypeAdapter(model).validate_python(dict(req.headers))

    def validate_response(self, obj: Any, model: type[BaseModel]) -> Any:
        if isinstance(obj, model):
            return obj
        elif isinstance(obj, dict):
            return model.model_validate(obj)
        else:
            raise TypeError(f"Expected {model.__name__} or dict, got {type(obj).__name__}")

    def serialize(self, obj: Any) -> tuple[str | bytes, str]:
        content: str | bytes
        content_type: str
        if isinstance(obj, BaseModel):
            content = obj.model_dump_json()
            content_type = "application/json"
        elif isinstance(obj, (dict, list)):
            content = json.dumps(obj)
            content_type = "application/json"
        elif isinstance(obj, str):
            content = obj.encode("utf-8")
            content_type = "text/plain; charset=utf-8"
        elif isinstance(obj, bytes):
            content = obj
            content_type = "application/octet-stream"
        else:
            raise TypeError(f"Cannot serialize type {type(obj).__name__}")
        return content, content_type

    def format_error(self, exc: Exception) -> dict[str, Any]:
        if isinstance(exc, PydanticValidationError):
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
            return {"detail": [{"loc": [], "msg": str(exc), "type": "value_error"}]}

    def _map_error_type(self, pydantic_type: str) -> str:
        if "missing" in pydantic_type:
            return "missing"
        return pydantic_type