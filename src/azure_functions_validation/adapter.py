"""Validation adapter layer for request/response validation."""

from collections.abc import Callable
import dataclasses
import json
from typing import Any, Protocol, get_origin
from urllib.parse import parse_qs, urlsplit

from azure.functions import HttpRequest
from pydantic import BaseModel, ConfigDict, TypeAdapter
from pydantic import ValidationError as PydanticValidationError
from pydantic_core import PydanticSerializationError

from .errors import AdapterValidationError, MalformedRequestError, SerializationError


def _prefix_loc(source: str | None, loc: list[Any], *, legacy_loc: bool) -> list[Any]:
    """Prepend the input *source* segment to a Pydantic ``loc`` tuple.

    Produces source-disambiguated locations such as ``["body", "email"]`` so
    that body/query/path/header collisions are distinguishable.  When
    *legacy_loc* is ``True`` (or *source* is ``None``) the raw ``loc`` is
    returned unchanged for one-cycle backward compatibility.
    """
    if legacy_loc or source is None:
        return loc
    return [source, *loc]


def _is_dataclass_instance(obj: Any) -> bool:
    return dataclasses.is_dataclass(obj) and not isinstance(obj, type)


_JSON_TYPE_ADAPTER = TypeAdapter(Any, config=ConfigDict(ser_json_inf_nan="null"))


def _dump_json(value: Any) -> str:
    try:
        compatible = _JSON_TYPE_ADAPTER.dump_python(
            value,
            mode="json",
            fallback=lambda unsupported: (_ for _ in ()).throw(
                SerializationError(type(unsupported).__name__)
            ),
        )
        return json.dumps(compatible)
    except PydanticSerializationError as exc:
        if isinstance(exc.__cause__, SerializationError):
            raise exc.__cause__ from exc
        raise SerializationError(type(value).__name__) from exc


# Ordered serialization dispatch table: (type predicate, serializer).
# The first matching predicate wins, mirroring the previous isinstance ladder.
_SERIALIZERS: tuple[tuple[Callable[[Any], bool], Callable[[Any], tuple[str | bytes, str]]], ...] = (
    (lambda o: isinstance(o, BaseModel), lambda o: (o.model_dump_json(), "application/json")),
    (
        lambda o: isinstance(o, (dict, list)),
        lambda o: (_dump_json(o), "application/json"),
    ),
    (lambda o: isinstance(o, str), lambda o: (o, "text/plain; charset=utf-8")),
    (lambda o: isinstance(o, bytes), lambda o: (o, "application/octet-stream")),
    (
        lambda o: isinstance(o, (int, float, bool)),
        lambda o: (_dump_json(o), "application/json"),
    ),
    (
        _is_dataclass_instance,
        lambda o: (_dump_json(dataclasses.asdict(o)), "application/json"),
    ),
)


class ValidationAdapter(Protocol):
    """Public validation backend contract.

    One adapter instance is created at decoration time and reused across
    concurrent invocations, so implementations must be stateless or thread-safe.
    Unexpected method exceptions are logged and returned as sanitized HTTP 500
    responses by the pipeline.
    """

    def parse_body(self, req: HttpRequest, model: Any) -> Any:
        """Parse and validate request body.

        Args:
            req: Azure Functions HttpRequest
            model: Pydantic model class to validate against

        Returns:
            Validated model instance

        Raises:
            MalformedRequestError: If client input is syntactically malformed (HTTP 400).
            AdapterValidationError: If body validation fails (HTTP 422).
            Exception: Any other failure is treated as an adapter fault (HTTP 500).
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
            MalformedRequestError: If client input is syntactically malformed (HTTP 400).
            AdapterValidationError: If validation fails (HTTP 422).
            Exception: Any other failure is treated as an adapter fault (HTTP 500).
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
            MalformedRequestError: If client input is syntactically malformed (HTTP 400).
            AdapterValidationError: If validation fails (HTTP 422).
            Exception: Any other failure is treated as an adapter fault (HTTP 500).
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
            MalformedRequestError: If client input is syntactically malformed (HTTP 400).
            AdapterValidationError: If validation fails (HTTP 422).
            Exception: Any other failure is treated as an adapter fault (HTTP 500).
        """
        ...

    def validate_response(
        self,
        obj: Any,
        model: Any,
        *,
        type_adapter: TypeAdapter[Any] | None = None,
    ) -> Any:
        """Validate response object against model.

        Args:
            obj: Response object (BaseModel instance, dict, list, etc.)
            model: Pydantic model class or generic type (e.g. list[SomeModel]) to validate against
            type_adapter: Optional pre-built TypeAdapter for reuse.

        Returns:
            Validated model instance

        Raises:
            AdapterValidationError: If validation fails (HTTP 500 for responses).
            Exception: Any other failure is an adapter fault (HTTP 500).
        """
        ...

    def serialize(self, obj: Any) -> tuple[str | bytes, str]:
        """Serialize response object to content and content-type.

        Args:
            obj: Object to serialize

        Returns:
            Tuple of content (``str`` or ``bytes``) and a non-empty HTTP
            content-type string. ``None`` is handled as 204 before this method.

        Raises:
            SerializationError: If object type is not supported
            Exception: Any other failure is an adapter fault (HTTP 500).
        """
        ...

    def format_error(self, exc: Exception) -> dict[str, Any]:
        """Format exception into standardized error response.

        Args:
            exc: Exception to format

        Returns:
            JSON-serializable error response dict with a ``detail`` list.

        Notes:
            A handler-level formatter takes precedence. This method formats the
            remaining default 4xx errors; 5xx errors are sanitized upstream.
        """
        ...


class PydanticAdapter:
    """Concrete validation adapter implementation using Pydantic v2."""

    def __init__(self, *, legacy_loc: bool = False) -> None:
        """Initialize the adapter.

        Args:
            legacy_loc: When ``True``, error ``loc`` values are emitted without
                the leading input-source segment (``["email"]`` instead of
                ``["body", "email"]``).  This is a one-cycle migration escape
                hatch and will be removed in a future release.
        """
        self._legacy_loc = legacy_loc

    @staticmethod
    def _to_adapter_error(
        exc: PydanticValidationError,
        *,
        source: str | None = None,
        legacy_loc: bool = False,
    ) -> AdapterValidationError:
        """Convert a Pydantic ``ValidationError`` into an ``AdapterValidationError``.

        The library-specific exception is preserved as ``__cause__`` while the
        normalized ``errors`` list keeps the pipeline and downstream callers
        decoupled from Pydantic.  When *source* is provided, each ``loc`` is
        prefixed with it (unless *legacy_loc* is set).
        """
        detail = [
            {
                "loc": _prefix_loc(source, list(error["loc"]), legacy_loc=legacy_loc),
                "msg": error["msg"],
                "type": error["type"],
            }
            for error in exc.errors()
        ]
        return AdapterValidationError(str(exc), detail)

    def _source_error(self, exc: PydanticValidationError, source: str) -> AdapterValidationError:
        """Convert *exc*, prefixing ``loc`` with *source* per ``legacy_loc``."""
        return self._to_adapter_error(exc, source=source, legacy_loc=self._legacy_loc)

    @staticmethod
    def _missing_body_validation_error() -> AdapterValidationError:
        # The underlying Pydantic model and its validation error are built once
        # at import time (see ``_MISSING_BODY_ERROR`` below).  A fresh exception
        # is returned per call so callers never share mutable error state.
        message, detail = _MISSING_BODY_ERROR
        return AdapterValidationError(message, [dict(entry) for entry in detail])

    def parse_body(self, req: HttpRequest, model: Any) -> Any:
        """Parse and validate request body from JSON.

        Args:
            req: Azure Functions HttpRequest
            model: Pydantic model class to validate against

        Returns:
            Validated model instance

        Raises:
            MalformedRequestError: If JSON or UTF-8 decoding is invalid.
            AdapterValidationError: If body is missing or validation fails.
        """
        body = req.get_body()

        # Handle empty body
        if not body:
            raise self._missing_body_validation_error()

        # Parse JSON
        try:
            body_str = body.decode("utf-8")
        except UnicodeDecodeError as e:
            raise MalformedRequestError("Invalid JSON") from e

        if not body_str.strip():
            # Empty JSON string - this is a missing body, not invalid JSON
            raise self._missing_body_validation_error()

        try:
            data = json.loads(body_str)
        except json.JSONDecodeError as e:
            raise MalformedRequestError("Invalid JSON") from e

        # Validate with Pydantic
        try:
            return TypeAdapter(model).validate_python(data)
        except PydanticValidationError as exc:
            raise self._source_error(exc, "body") from exc

    def parse_query(self, req: HttpRequest, model: type[BaseModel]) -> Any:
        """Parse and validate query parameters.

        Args:
            req: Azure Functions HttpRequest
            model: Pydantic model class to validate against

        Returns:
            Validated model instance

        Raises:
            AdapterValidationError: If validation fails
        """
        query_data = dict(req.params or {})
        url_values = parse_qs(urlsplit(getattr(req, "url", "")).query, keep_blank_values=True)
        query_data.update({key: values for key, values in url_values.items() if len(values) > 1})
        for name, field in model.model_fields.items():
            key = field.alias or name
            if get_origin(field.annotation) is list and key in query_data:
                value = query_data[key]
                if not isinstance(value, list):
                    query_data[key] = [value]

        # Validate with Pydantic
        try:
            return model.model_validate(query_data)
        except PydanticValidationError as exc:
            raise self._source_error(exc, "query") from exc

    def parse_path(self, req: HttpRequest, model: type[BaseModel]) -> Any:
        """Parse and validate path parameters.

        Args:
            req: Azure Functions HttpRequest
            model: Pydantic model class to validate against

        Returns:
            Validated model instance

        Raises:
            AdapterValidationError: If validation fails
        """
        # Parse route parameters
        route_params = req.route_params or {}

        # Validate with Pydantic
        try:
            return model.model_validate(route_params)
        except PydanticValidationError as exc:
            raise self._source_error(exc, "path") from exc

    def parse_headers(self, req: HttpRequest, model: type[BaseModel]) -> Any:
        """Parse and validate headers.

        Args:
            req: Azure Functions HttpRequest
            model: Pydantic model class to validate against

        Returns:
            Validated model instance

        Raises:
            AdapterValidationError: If validation fails
        """
        # Parse headers
        headers = req.headers or {}

        field_keys = {
            candidate.casefold(): field.alias or name
            for name, field in model.model_fields.items()
            for candidate in (name, field.alias)
            if isinstance(candidate, str)
        }
        header_data = {field_keys.get(key.casefold(), key): value for key, value in headers.items()}

        # Validate with Pydantic
        try:
            return model.model_validate(header_data)
        except PydanticValidationError as exc:
            raise self._source_error(exc, "headers") from exc

    def validate_response(
        self,
        obj: Any,
        model: Any,
        *,
        type_adapter: TypeAdapter[Any] | None = None,
    ) -> Any:
        """Validate response object against model.

        Uses ``TypeAdapter`` to support both concrete ``BaseModel`` subclasses
        and parameterized generic types such as ``list[SomeModel]``.

        When *type_adapter* is provided (pre-built at decoration time), it is
        reused to avoid per-request allocation.

        Args:
            obj: Response object (BaseModel instance, dict, list, etc.)
            model: Pydantic model class or generic type (e.g. list[SomeModel]) to validate against
            type_adapter: Optional pre-built TypeAdapter for reuse.

        Returns:
            Validated model instance

        Raises:
            AdapterValidationError: If validation fails
        """
        ta = type_adapter if type_adapter is not None else TypeAdapter(model)
        try:
            return ta.validate_python(obj)
        except PydanticValidationError as exc:
            raise self._source_error(exc, "response") from exc

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
        for predicate, serializer in _SERIALIZERS:
            if predicate(obj):
                return serializer(obj)
        raise SerializationError(type(obj).__name__)

    def format_error(self, exc: Exception) -> dict[str, Any]:
        """Format exception into standardized error response.

        Args:
            exc: Exception to format (typically AdapterValidationError)

        Returns:
            Error response dict with 'detail' key containing list of errors
        """
        if isinstance(exc, AdapterValidationError):
            return {"detail": exc.errors}
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
                        "loc": ["body"] if isinstance(exc, MalformedRequestError) else [],
                        "msg": str(exc),
                        "type": "value_error",
                    }
                ]
            }


def _compute_missing_body_error() -> tuple[str, list[dict[str, Any]]]:
    """Build the missing-body validation error once, at import time.

    Creating a Pydantic model class is relatively expensive; hoisting it out of
    the per-request hot path avoids re-creating it on every empty-body request.
    The resulting ``(message, detail)`` pair is reused to construct fresh
    :class:`AdapterValidationError` instances with identical ``loc``/``msg``/
    ``type`` output.
    """

    class _MissingBodyPayload(BaseModel):
        body: Any

    try:
        _MissingBodyPayload.model_validate({})
    except PydanticValidationError as exc:
        adapter_error = PydanticAdapter._to_adapter_error(exc)
        return str(exc), adapter_error.errors

    raise RuntimeError("Unreachable: expected missing body validation error")


_MISSING_BODY_ERROR: tuple[str, list[dict[str, Any]]] = _compute_missing_body_error()
