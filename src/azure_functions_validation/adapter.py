"""Validation adapter layer for request/response validation."""

import json
from typing import Any, Protocol, Type

from azure.functions import HttpRequest
from pydantic import BaseModel, TypeAdapter
from pydantic import ValidationError as PydanticValidationError

from .exceptions import ResponseValidationError


class ValidationAdapter(Protocol):
    """Protocol defining the interface for validation adapters."""

    def parse_body(self, req: HttpRequest, model: Type[BaseModel]) -> Any: ...
    def parse_query(self, req: HttpRequest, model: Type[BaseModel]) -> Any: ...
    def parse_path(self, req: HttpRequest, model: Type[BaseModel]) -> Any: ...
    def parse_headers(self, req: HttpRequest, model: Type[BaseModel]) -> Any: ...
    def validate_response(self, obj: Any, model: Type[Any]) -> Any: ...
    def serialize(self, obj: Any) -> tuple[str | bytes, str]: ...
    def format_error(self, exc: Exception, loc_prefix: tuple[str, ...]) -> dict[str, Any]: ...


class PydanticAdapter:
    """Concrete validation adapter implementation using Pydantic v2."""

    def parse_body(self, req: HttpRequest, model: Type[BaseModel]) -> Any:
        body = req.get_body()
        if not body:
            raise PydanticValidationError.from_exception_data(
                "Missing Body", [{"type": "missing", "loc": (), "input": None}]
            )
        try:
            data = json.loads(body)
        except json.JSONDecodeError as e:
            raise ValueError("Invalid JSON in body") from e
        
        return TypeAdapter(model).validate_python(data)

    def parse_query(self, req: HttpRequest, model: Type[BaseModel]) -> Any:
        return TypeAdapter(model).validate_python(req.params)

    def parse_path(self, req: HttpRequest, model: Type[BaseModel]) -> Any:
        return TypeAdapter(model).validate_python(req.route_params)

    def parse_headers(self, req: HttpRequest, model: Type[BaseModel]) -> Any:
        return TypeAdapter(model).validate_python(dict(req.headers))

    def validate_response(self, obj: Any, model: Type[Any]) -> Any:
        try:
            return TypeAdapter(model).validate_python(obj)
        except PydanticValidationError as e:
            raise ResponseValidationError from e

    def serialize(self, obj: Any) -> tuple[str | bytes, str]:
        if isinstance(obj, BaseModel):
            return obj.model_dump_json(), "application/json"
        if isinstance(obj, (dict, list)):
            return json.dumps(obj), "application/json"
        if isinstance(obj, str):
            return obj.encode("utf-8"), "text/plain; charset=utf-8"
        if isinstance(obj, bytes):
            return obj, "application/octet-stream"
        
        try:
            ta = TypeAdapter(type(obj))
            return ta.dump_json(obj), "application/json"
        except Exception:
            return str(obj).encode("utf-8"), "text/plain; charset=utf-8"

    def format_error(self, exc: Exception, loc_prefix: tuple[str, ...]) -> dict[str, Any]:
        if isinstance(exc, PydanticValidationError):
            detail = []
            for error in exc.errors():
                error_type = self._map_error_type(error["type"])
                detail.append(
                    {
                        "loc": list(loc_prefix) + list(error.get("loc", ())),
                        "msg": error["msg"],
                        "type": error_type,
                    }
                )
            return {"detail": detail}
        elif isinstance(exc, ValueError):
            return {"detail": [{"loc": list(loc_prefix), "msg": str(exc), "type": "json_invalid"}]}
        elif isinstance(exc, ResponseValidationError):
            return self.format_error(exc.__cause__, loc_prefix)
        else:
            return {
                "detail": [
                    {"loc": list(loc_prefix), "msg": str(exc), "type": "internal_error"}
                ]
            }

    def _map_error_type(self, pydantic_type: str) -> str:
        if "missing" in pydantic_type:
            return "missing"
        return pydantic_type