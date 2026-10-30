"""Builder for the cross-package ``endpoint`` metadata namespace.

``validate_http`` writes two namespaces onto the wrapped handler under the
shared ``_azure_functions_metadata`` convention attribute:

* ``"validation"`` — this package's own request/response model references
  (kept for the deprecation cycle; see :mod:`._metadata`).
* ``"endpoint"`` — this package's local, OpenAPI-ready endpoint payload,
  consumed by ``azure-functions-openapi``. Unlike the ``validation`` namespace
  (which carries Pydantic model *classes*), the ``endpoint`` payload is entirely
  *self-contained* JSON Schema: the consumer needs no import of this package
  and no access to the user's model classes.

This package's payload shape and canonicalization rules are checked against
``schemas/endpoint.schema.json`` — a local conformance artifact — and
documented in ``docs/METADATA_SPEC.md``.
"""

from __future__ import annotations

from typing import Any, TypedDict

from pydantic import BaseModel, TypeAdapter

from ._metadata import _merge_namespace
from .schemas import ENDPOINT_METADATA_VERSION, _contains_ref

#: Namespace for this package's local endpoint payload.
ENDPOINT_NAMESPACE = "endpoint"

#: Pydantic ref template used by this producer so ``$defs`` stay unresolved and
#: the consumer (openapi) remains the sole ``$ref``-collision authority.
_REF_TEMPLATE = "#/$defs/{model}"

#: HTTP status code under which the standardized validation-error response is
#: documented. Emitted whenever request validation can fail (any of
#: ``body``/``query``/``path``/``headers`` is a model).
_VALIDATION_ERROR_STATUS = "422"


def _validation_error_schema() -> dict[str, Any]:
    """Return a self-contained JSON Schema for the ``{"detail": [...]}`` envelope.

    Mirrors the runtime 422 body produced by the pipeline (see
    ``pipeline.format_error_response``): a ``detail`` array of items with
    ``loc`` / ``msg`` / ``type``. A fresh dict is built on every call so
    consumers may mutate the embedded schema freely without cross-handler
    aliasing. Contains no ``$ref``, so the ``$defs``-if-``$ref`` rule does not
    apply.
    """
    return {
        "type": "object",
        "properties": {
            "detail": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "loc": {
                            "type": "array",
                            "items": {"type": ["string", "integer"]},
                        },
                        "msg": {"type": "string"},
                        "type": {"type": "string"},
                    },
                    "required": ["loc", "msg", "type"],
                },
            }
        },
        "required": ["detail"],
    }


class EndpointMetadata(TypedDict, total=False):
    """Shape of ``_azure_functions_metadata["endpoint"]`` (schema version 1)."""

    version: int
    request_body: dict[str, Any] | None
    request_body_required: bool
    parameters: list[dict[str, Any]]
    responses: dict[str, dict[str, Any]] | None


def _is_model_type(model: Any) -> bool:
    """Return ``True`` if *model* is a Pydantic ``BaseModel`` subclass."""
    return isinstance(model, type) and issubclass(model, BaseModel)


def _annotation_schema(
    annotation: Any, mode: str, *, by_alias: bool = True
) -> dict[str, Any] | None:
    """Best-effort JSON Schema for any Pydantic-constructible annotation.

    The runtime validates and serializes ``body``/``response_model`` through
    ``TypeAdapter`` unconditionally (see ``adapter.py`` / ``decorator.py``),
    so it already accepts far more than direct ``BaseModel`` subclasses --
    ``list[Model]``, ``Optional[Model]``, ``Union[...]``, and ``Annotated``
    forms all work at request time (#452). ``TypeAdapter(X).json_schema(...)``
    produces byte-identical output to ``X.model_json_schema(...)`` for a
    direct ``BaseModel`` subclass, so this generalizes ``_model_schema``
    without changing existing output.

    Returns ``None`` when *annotation* is ``None`` (not configured) or when
    no schema can be derived at all -- a custom ``ValidationAdapter`` backend
    may pass a non-Pydantic marker through ``body``/``query``/``path``/
    ``headers`` that only that backend understands (#537), and this must stay
    silently absent from the metadata exactly as before, not raise.
    """
    if annotation is None:
        return None
    try:
        return TypeAdapter(annotation).json_schema(
            by_alias=by_alias,
            ref_template=_REF_TEMPLATE,
            mode=mode,  # type: ignore[arg-type]
        )
    except Exception:
        return None


def _split_nullable_schema(schema: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Split a response schema into its non-null variant and nullability.

    A nullable response annotation (e.g. ``Optional[Model]``) produces a
    top-level ``anyOf`` with a ``{"type": "null"}`` member. The runtime's own
    response handling makes the identical split: a validated ``None`` result
    short-circuits to an empty ``204`` response instead of ever serializing a
    ``null`` body under the success status (``pipeline._build_response``).
    Mirroring that here keeps the documented success-status schema truthful
    (it never actually carries a ``null`` body) while still recording the
    real ``204`` outcome (#537).

    Returns the schema unchanged with ``False`` when there is no top-level
    nullable branch to split out.
    """
    any_of = schema.get("anyOf")
    if not isinstance(any_of, list):
        return schema, False
    non_null = [m for m in any_of if not (isinstance(m, dict) and m.get("type") == "null")]
    if len(non_null) == len(any_of):
        return schema, False
    other_keys = {k: v for k, v in schema.items() if k != "anyOf"}
    if len(non_null) == 1:
        return {**other_keys, **non_null[0]}, True
    return {**other_keys, "anyOf": non_null}, True


def _model_schema(model: type[BaseModel], mode: str, *, by_alias: bool = True) -> dict[str, Any]:
    """Generate a model's JSON Schema using the SPEC-pinned canonicalization."""
    return model.model_json_schema(
        by_alias=by_alias,
        ref_template=_REF_TEMPLATE,
        mode=mode,  # type: ignore[arg-type]
    )


def _attach_defs_if_ref(
    field_schema: dict[str, Any],
    defs: dict[str, Any] | None,
) -> dict[str, Any]:
    """Attach ``$defs`` to a per-field schema when it uses a ``$ref``.

    Keeps the SPEC's ``$defs``-if-``$ref`` invariant intact for parameter
    schemas that reference a nested model, so the consumer can hoist them.
    """
    if defs and _contains_ref(field_schema):
        merged = dict(field_schema)
        merged["$defs"] = defs
        return merged
    return field_schema


def _build_parameters(model: type[BaseModel], location: str) -> list[dict[str, Any]]:
    """Build OpenAPI parameter objects from a query/path/header model.

    Parameter ``name`` uses the field's inbound validation alias (``by_alias=True``)
    so it matches the wire contract. ``path`` parameters are always required.
    """
    schema = _model_schema(model, "validation")
    properties: dict[str, Any] = schema.get("properties", {})
    required_names = set(schema.get("required", []))
    defs = schema.get("$defs")

    params: list[dict[str, Any]] = []
    for name, field_schema in properties.items():
        params.append(
            {
                "name": name,
                "in": location,
                "required": location == "path" or name in required_names,
                "schema": _attach_defs_if_ref(dict(field_schema), defs),
            }
        )
    return params


def build_endpoint_metadata(config: Any) -> EndpointMetadata:
    """Build the ``endpoint`` namespace payload from a pipeline config.

    ``config`` exposes ``body``, ``query``, ``path``, ``headers``,
    ``response_model``, and ``success_status_code``.
    """
    body = config.body
    request_body = _annotation_schema(body, "validation")
    if request_body is not None:
        # The runtime adapter unconditionally rejects an empty body (422) whenever
        # a body model is configured, regardless of individual field optionality,
        # so the metadata must report the body as required to stay truthful to
        # actual server behaviour (#347). Optional-body support, if ever added,
        # must be an explicit opt-in that also relaxes the runtime 422. See the
        # durable design note: docs/design/optional-body-347.md.
        request_body_required = True
    else:
        request_body_required = False

    parameters: list[dict[str, Any]] = []
    has_request_model = False
    sources: tuple[tuple[Any, str], ...] = (
        (config.query, "query"),
        (getattr(config, "query_params_model", None), "query"),
        (config.path, "path"),
        (config.headers, "header"),
    )
    for model, location in sources:
        if _is_model_type(model):
            has_request_model = True
            parameters.extend(_build_parameters(model, location))

    # A request body model also makes request validation (and thus a 422) possible.
    has_request_model = has_request_model or request_body is not None

    responses: dict[str, dict[str, Any]] = {}
    response_model = config.response_model
    response_schema = _annotation_schema(
        response_model, "serialization", by_alias=getattr(config, "response_by_alias", True)
    )
    if response_schema is not None:
        status = str(getattr(config, "success_status_code", 200) or 200)
        non_null_schema, is_nullable = _split_nullable_schema(response_schema)
        responses[status] = {"schema": non_null_schema}
        if is_nullable:
            # A validated None result short-circuits to an empty 204, never a
            # 200-with-null-body (pipeline._build_response) -- document the
            # real outcome alongside the non-null success schema (#537).
            responses["204"] = {}
    if has_request_model:
        # Document the standardized validation-error contract the runtime emits
        # on invalid input, so consumers (openapi) need not hand-author it.
        responses[_VALIDATION_ERROR_STATUS] = {"schema": _validation_error_schema()}

    payload: EndpointMetadata = {
        "version": ENDPOINT_METADATA_VERSION,
        "request_body": request_body,
        "request_body_required": request_body_required,
        "parameters": parameters,
        "responses": responses or None,
    }
    return payload


def set_endpoint_metadata(wrapper: Any, source: Any, payload: EndpointMetadata) -> None:
    """Merge the ``endpoint`` namespace onto *wrapper* without clobbering others.

    Seeds from any existing convention attribute on *source* (e.g. the
    ``validation`` namespace already written by this decorator), merges in
    *payload* under the ``endpoint`` namespace, and writes the result onto
    *wrapper*.
    """
    _merge_namespace(wrapper, source, ENDPOINT_NAMESPACE, payload)
