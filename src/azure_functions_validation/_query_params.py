"""Decoration-time construction of explicit, flat query parameter models."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
import inspect
import types
from typing import Any, get_args, get_origin, get_type_hints

from pydantic import BaseModel, ConfigDict, Field, create_model
from pydantic.errors import PydanticUserError
from pydantic.fields import FieldInfo

_RESERVED = frozenset({"context", "http_request", "body", "query", "path", "headers", "req_model"})


def _is_sdk_annotation(annotation: Any) -> bool:
    lineage = annotation.__mro__ if inspect.isclass(annotation) else (annotation,)
    return any(
        str(getattr(candidate, "__module__", "")).startswith("azure.") for candidate in lineage
    ) or any(
        _is_sdk_annotation(arg)
        for arg in (get_origin(annotation), *get_args(annotation))
        if arg is not None
    )


def _flat_schema(schema: dict[str, Any], defs: dict[str, Any], *, array: bool = True) -> bool:
    if "$ref" in schema:
        return _flat_schema(defs[schema["$ref"].rsplit("/", 1)[1]], defs, array=array)
    variants = schema.get("anyOf", schema.get("oneOf"))
    if variants is not None:
        return all(_flat_schema(item, defs, array=array) for item in variants)
    if schema.get("type") == "array":
        return array and _flat_schema(schema.get("items", {}), defs, array=False)
    return schema.get("type") in {"string", "integer", "number", "boolean", "null"}


def build_query_params(
    func: Callable[..., Any], declarations: Mapping[str, Any], request_name: str
) -> tuple[type[BaseModel], tuple[str, ...]]:
    """Copy explicit declarations into one reusable model or reject ambiguous input.

    Resolve each annotation independently against the handler's globals so an
    unrelated application-injection annotation cannot poison query declarations.
    """
    parameters = inspect.signature(func).parameters
    fields: dict[str, Any] = {}
    inbound_names: set[str] = set()
    for name, declaration in declarations.items():
        if name in _RESERVED or name == request_name:
            raise ValueError(f"query_params name {name!r} is reserved")
        parameter = parameters.get(name)
        if parameter is None or parameter.kind is not inspect.Parameter.KEYWORD_ONLY:
            raise ValueError(f"query_params {name!r} requires an explicit keyword-only parameter")
        if name.startswith("_") or hasattr(BaseModel, name):
            raise ValueError(f"query_params {name!r} is not a supported Pydantic field name")
        if isinstance(parameter.default, FieldInfo):
            raise ValueError(
                f"query_params {name!r}: put Field metadata in Annotated, not the default"
            )

        probe = types.FunctionType((lambda: None).__code__, func.__globals__)
        probe.__annotations__ = {"declaration": declaration}
        if parameter.annotation is not inspect.Parameter.empty:
            probe.__annotations__["handler"] = parameter.annotation
        try:
            hints = get_type_hints(probe, include_extras=True)
        except (NameError, TypeError) as exc:
            raise ValueError(f"query_params {name!r}: cannot resolve annotation") from exc
        if _is_sdk_annotation(hints.get("handler")):
            raise ValueError(f"query_params {name!r} cannot replace an Azure SDK binding")

        info = FieldInfo.from_annotation(hints["declaration"])
        if parameter.default is not inspect.Parameter.empty and not info.is_required():
            raise ValueError(f"query_params {name!r}: defaults supplied in both places")
        if info.validation_alias is not None and not isinstance(info.validation_alias, str):
            raise ValueError(f"query_params {name!r} requires one flat string validation alias")
        wire_name = (
            info.validation_alias
            if info.validation_alias is not None
            else info.alias
            if info.alias is not None
            else name
        )
        if not wire_name:
            raise ValueError(f"query_params {name!r} requires a non-empty inbound name")
        if wire_name in inbound_names or (wire_name != name and wire_name in declarations):
            raise ValueError(f"query_params {name!r}: ambiguous inbound alias {wire_name!r}")
        inbound_names.add(wire_name)
        # An assigned ``Field`` overrides the declaration's own metadata, so the shorthand's
        # default policy holds even when the declaration sets ``validate_default=False``.
        # Passing only an annotation and a ``Field`` keeps this independent of how a
        # Pydantic version copies ``FieldInfo``.
        default_policy: dict[str, Any] = {"validate_default": True}
        if parameter.default is not inspect.Parameter.empty:
            default_policy["default"] = deepcopy(parameter.default)
        fields[name] = (hints["declaration"], Field(**default_policy))

    try:
        model = create_model(
            f"{func.__name__}QueryParams",
            __config__=ConfigDict(
                extra="ignore",
                validate_by_alias=True,
                validate_by_name=False,
                validate_default=True,
            ),
            __module__=func.__module__,
            **fields,
        )
        model.model_rebuild(_types_namespace=func.__globals__)
        schema = model.model_json_schema(mode="validation")
    except (TypeError, ValueError, NameError, PydanticUserError) as exc:
        raise ValueError("query_params requires supported flat Pydantic annotations") from exc
    defs = schema.get("$defs", {})
    if not all(_flat_schema(item, defs) for item in schema["properties"].values()):
        raise ValueError("query_params supports only scalars, scalar unions, and flat lists")
    return model, tuple(fields)
