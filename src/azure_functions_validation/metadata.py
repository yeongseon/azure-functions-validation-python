"""Public metadata helpers for validation contracts."""

import typing
from typing import Any

from pydantic import TypeAdapter


def _type_name(contract_type: Any) -> str:
    origin = typing.get_origin(contract_type)
    if origin is not None:
        args = typing.get_args(contract_type)
        arg_names = ", ".join(_type_name(a) for a in args)
        origin_name = getattr(origin, "__name__", repr(origin))
        return f"{origin_name}[{arg_names}]" if arg_names else origin_name
    return getattr(contract_type, "__name__", repr(contract_type))


def get_contract_schema(contract_type: Any) -> dict[str, Any]:
    """Return a JSON schema for a validated request or response type."""
    return TypeAdapter(contract_type).json_schema()


def _build_422_error_schema() -> dict[str, Any]:
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
                            "items": {"type": "string"},
                            "description": "Location of error",
                        },
                        "msg": {
                            "type": "string",
                            "description": "Error message",
                        },
                        "type": {
                            "type": "string",
                            "description": "Error type identifier",
                        },
                    },
                },
            }
        },
    }


def _build_422_error_examples(request_model: Any) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    schema = get_contract_schema(request_model)

    properties = schema.get("properties", {})
    required_fields = set(schema.get("required", []))

    for field_name, field_schema in properties.items():
        if field_name in required_fields:
            examples.append(
                {
                    "summary": f"Missing required field: {field_name}",
                    "value": {
                        "detail": [
                            {
                                "loc": ["body", field_name],
                                "msg": "Field required",
                                "type": "missing",
                            }
                        ]
                    },
                }
            )

        if field_schema.get("type") == "string":
            if "minLength" in field_schema:
                examples.append(
                    {
                        "summary": f"String too short: {field_name}",
                        "value": {
                            "detail": [
                                {
                                    "loc": ["body", field_name],
                                    "msg": (
                                        "String should have at least "
                                        f"{field_schema['minLength']} character(s)"
                                    ),
                                    "type": "string_too_short",
                                }
                            ]
                        },
                    }
                )
            if "pattern" in field_schema:
                examples.append(
                    {
                        "summary": f"Pattern mismatch: {field_name}",
                        "value": {
                            "detail": [
                                {
                                    "loc": ["body", field_name],
                                    "msg": (
                                        "String should match pattern "
                                        f"'{field_schema['pattern']}'"
                                    ),
                                    "type": "string_pattern_mismatch",
                                }
                            ]
                        },
                    }
                )

        if field_schema.get("type") in {"integer", "number"}:
            if "minimum" in field_schema or "exclusiveMinimum" in field_schema:
                examples.append(
                    {
                        "summary": f"Value too small: {field_name}",
                        "value": {
                            "detail": [
                                {
                                    "loc": ["body", field_name],
                                    "msg": "Value is too small",
                                    "type": "too_small",
                                }
                            ]
                        },
                    }
                )
            if "maximum" in field_schema or "exclusiveMaximum" in field_schema:
                examples.append(
                    {
                        "summary": f"Value too large: {field_name}",
                        "value": {
                            "detail": [
                                {
                                    "loc": ["body", field_name],
                                    "msg": "Value is too large",
                                    "type": "too_large",
                                }
                            ]
                        },
                    }
                )

    return examples


def get_request_contract_metadata(
    *,
    body: Any | None = None,
    query: Any | None = None,
    path: Any | None = None,
    headers: Any | None = None,
    request_model: Any | None = None,
) -> dict[str, Any]:
    """Describe the validated request sources exposed by this package."""
    if request_model is not None and body is not None:
        raise ValueError("Cannot use request_model together with body")
    request_body = request_model or body
    sources: dict[str, dict[str, Any]] = {}

    for source_name, contract_type in (
        ("body", request_body),
        ("query", query),
        ("path", path),
        ("headers", headers),
    ):
        if contract_type is None:
            continue
        sources[source_name] = {
            "type": _type_name(contract_type),
            "schema": get_contract_schema(contract_type),
        }

    return {"sources": sources}


def get_response_contract_metadata(response_model: Any | None) -> dict[str, Any] | None:
    """Describe the validated response contract exposed by this package."""
    if response_model is None:
        return None

    return {
        "type": _type_name(response_model),
        "schema": get_contract_schema(response_model),
    }


def get_validation_error_contract(request_model: Any | None) -> dict[str, Any] | None:
    """Describe the standardized 422 validation error contract."""
    if request_model is None:
        return None

    return {
        "status_code": 422,
        "type": "validation_error",
        "schema": _build_422_error_schema(),
        "examples": _build_422_error_examples(request_model),
    }


def describe_validation_contract(
    *,
    body: Any | None = None,
    query: Any | None = None,
    path: Any | None = None,
    headers: Any | None = None,
    request_model: Any | None = None,
    response_model: Any | None = None,
) -> dict[str, Any]:
    """Return a combined description of request, response, and 422 error contracts."""
    request_metadata = get_request_contract_metadata(
        body=body,
        query=query,
        path=path,
        headers=headers,
        request_model=request_model,
    )
    request_body = request_model or body

    return {
        "request": request_metadata,
        "response": get_response_contract_metadata(response_model),
        "errors": {
            "validation": get_validation_error_contract(request_body),
        },
    }
