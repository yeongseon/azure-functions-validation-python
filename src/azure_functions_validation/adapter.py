"""Validation adapter layer for request/response validation."""

from collections.abc import Callable
import contextlib
import dataclasses
import json
import types
from typing import Annotated, Any, Protocol, Union, get_args, get_origin
from urllib.parse import parse_qs, urlsplit

from azure.functions import HttpRequest
from pydantic import AliasChoices, BaseModel, ConfigDict, TypeAdapter
from pydantic import ValidationError as PydanticValidationError
from pydantic.fields import FieldInfo
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


def _is_unambiguous_list_annotation(annotation: Any) -> bool:
    """Return ``True`` if *annotation* denotes a list and nothing else.

    Recognizes a direct ``list[T]``, the same wrapped in ``Annotated[...]``,
    and a nullable form (``list[T] | None`` / ``Optional[list[T]]``) -- #465
    fixed singleton-vs-repeated-key normalization for the direct case only;
    a nullable list has a ``Union`` origin, not ``list``, and fell through
    unnormalized (#540). A genuine scalar-or-list union (e.g. ``list[T] | int``)
    is deliberately left alone: query-string coercion cannot safely guess
    which branch a bare key/value pair was meant for.
    """
    origin = get_origin(annotation)
    if origin is list:
        return True
    if origin is Annotated:
        return _is_unambiguous_list_annotation(get_args(annotation)[0])
    if origin is Union or origin is types.UnionType:
        non_none_args = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(non_none_args) == 1:
            return _is_unambiguous_list_annotation(non_none_args[0])
    return False


def _inbound_candidates(field: FieldInfo, name: str) -> list[str]:
    """Return every wire-format name Pydantic will accept as inbound data
    for *field*, in Pydantic's own precedence order.

    ``validation_alias`` (a string, or each string member of an
    ``AliasChoices`` in the order Pydantic tries them) takes precedence --
    when both ``alias`` and ``validation_alias`` are set, Pydantic validates
    against ``validation_alias`` only, never the serialization-only
    ``alias``. ``alias`` (which Pydantic also uses for validation when
    ``validation_alias`` is not set separately) and the plain Python field
    name are included as further fallbacks, since request normalization
    cannot know this model's ``populate_by_name``/``validate_by_name``
    configuration without a prohibitively invasive lookup, and including an
    extra candidate that happens not to validate is harmless (#541).
    ``AliasPath`` entries are skipped: expanding a nested path into the flat
    HTTP query/header namespace is out of scope.
    """
    candidates: list[str] = []
    validation_alias = field.validation_alias
    if isinstance(validation_alias, str):
        candidates.append(validation_alias)
    elif isinstance(validation_alias, AliasChoices):
        candidates.extend(choice for choice in validation_alias.choices if isinstance(choice, str))
    if isinstance(field.alias, str) and field.alias not in candidates:
        candidates.append(field.alias)
    if name not in candidates:
        candidates.append(name)
    return candidates


_JSON_TYPE_ADAPTER = TypeAdapter(Any, config=ConfigDict(ser_json_inf_nan="null"))


def _dump_json(value: Any) -> str:
    # Plain JSON values are encoded in one pass. Anything json.dumps can't write
    # as standard JSON (other types, dict keys it rejects, NaN and infinities
    # via allow_nan=False, cycles, very deep nesting) goes through Pydantic,
    # which builds a JSON-compatible copy first.
    with contextlib.suppress(TypeError, ValueError, RecursionError):
        return json.dumps(value, allow_nan=False)
    return _dump_json_via_pydantic(value)


def _dump_json_via_pydantic(value: Any) -> str:
    try:
        compatible = _JSON_TYPE_ADAPTER.dump_python(
            value,
            mode="json",
            by_alias=True,
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

    def serialize_response(
        self,
        obj: Any,
        model: Any,
        *,
        type_adapter: TypeAdapter[Any] | None = None,
        by_alias: bool = True,
        exclude_none: bool = False,
        exclude_unset: bool = False,
    ) -> tuple[str | bytes, str]:
        """Serialize an already-validated response against its DECLARED model.

        Called instead of :meth:`serialize` whenever ``response_model=`` is
        configured, with the object :meth:`validate_response` already
        returned (#539). This distinction matters: ``obj`` may be an
        instance of a *subclass* of ``model`` carrying extra fields (e.g. a
        database row model extending a public response model), and
        serializing by ``obj``'s own runtime type -- as :meth:`serialize`
        does -- would leak those extra fields. A conforming implementation
        MUST serialize strictly according to ``model`` (excluding
        subclass-only fields) and MUST honor *by_alias*/*exclude_none*/
        *exclude_unset* consistently with the generated ``endpoint`` response
        schema (see #463, which this method's contract exists to preserve).

        Args:
            obj: The value :meth:`validate_response` returned (already
                validated against ``model``).
            model: The declared response model/type passed to
                :meth:`validate_response`.
            type_adapter: Optional pre-built ``TypeAdapter`` for ``model``,
                reused to avoid per-request allocation. ``None`` when ``model``
                could not be turned into one at decoration time (e.g. a
                non-Pydantic model for a custom backend) -- implementations
                that do not need it may ignore this hint entirely.
            by_alias: Serialize field names using their configured alias.
            exclude_none: Omit fields whose value is ``None``.
            exclude_unset: Omit fields that were never explicitly set.

        Returns:
            Tuple of content (``str`` or ``bytes``) and a non-empty HTTP
            content-type string. ``None`` is handled as 204 before this method.

        Raises:
            SerializationError: If the object cannot be serialized.
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
            if not _is_unambiguous_list_annotation(field.annotation):
                continue
            for key in _inbound_candidates(field, name):
                if key in query_data:
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

        field_keys: dict[str, str] = {}
        for name, field in model.model_fields.items():
            candidates = _inbound_candidates(field, name)
            canonical = candidates[0]
            for candidate in candidates:
                field_keys[candidate.casefold()] = canonical
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
            SerializationError: If object type is not supported or the value
                cannot be serialized (for example a reference cycle or nesting
                deeper than pydantic-core allows)
        """
        for predicate, serializer in _SERIALIZERS:
            if predicate(obj):
                try:
                    return serializer(obj)
                except (RecursionError, ValueError) as exc:
                    # pydantic-core reports cycles and its nesting limit as ValueError,
                    # and PydanticSerializationError is a ValueError subclass.
                    raise SerializationError(type(obj).__name__) from exc
        raise SerializationError(type(obj).__name__)

    def serialize_response(
        self,
        obj: Any,
        model: Any,
        *,
        type_adapter: TypeAdapter[Any] | None = None,
        by_alias: bool = True,
        exclude_none: bool = False,
        exclude_unset: bool = False,
    ) -> tuple[str | bytes, str]:
        """Serialize strictly according to the declared response model (#463, #539).

        Dumps through ``type_adapter`` (or a freshly built one for ``model``
        when not provided) rather than ``obj``'s own runtime type, so an
        ``obj`` that happens to be a subclass instance with extra fields
        never leaks them -- the same protection :meth:`serialize` cannot
        offer since it dispatches purely on ``obj``'s runtime type.
        """
        ta = type_adapter if type_adapter is not None else TypeAdapter(model)
        try:
            content = ta.dump_json(
                obj,
                by_alias=by_alias,
                exclude_none=exclude_none,
                exclude_unset=exclude_unset,
            )
        except (RecursionError, ValueError) as exc:
            raise SerializationError(type(obj).__name__) from exc
        return content, "application/json"

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
