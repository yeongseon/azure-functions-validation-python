# Custom Adapter Conformance

## Overview

A minimal in-memory custom `ValidationAdapter` that does **not** use Pydantic to validate, run
against the public `AdapterConformanceTests` helper. It implements every method of the
[adapter contract](../adapters.md#method-contract) as of the release that made
`serialize_response()` required (see
the [Troubleshooting](../troubleshooting.md) guide if an older adapter returns `500` after upgrading), and it is the starting point for adopters
writing their own backend.

It corresponds to `examples/custom_adapter/adapter.py` and `tests/test_custom_adapter_example.py`.

## The adapter

```python
"""A tiny in-memory custom ``ValidationAdapter`` that does not use Pydantic to validate (#637).

Models here are plain ``Schema`` objects (field name -> Python type). The adapter implements
every method of the public protocol, including ``serialize_response()``. It is deliberately
minimal: it exists to be run against ``AdapterConformanceTests``, not for production use.
"""

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, is_dataclass
import json
from typing import Any

from azure.functions import HttpRequest

from azure_functions_validation import (
    AdapterValidationError,
    MalformedRequestError,
    SerializationError,
)

_JSON = "application/json"


@dataclass(frozen=True)
class Schema:
    """A minimal stand-in for a model: required fields and the type each must coerce to."""

    fields: Mapping[str, type]


def _check(data: Any, schema: Schema, source: str, *, ci: bool = False) -> dict[str, Any]:
    """Validate *data* against *schema*; collect normalized ``loc``/``msg``/``type`` errors."""
    if not isinstance(data, Mapping):
        raise AdapterValidationError(
            "invalid", [{"loc": [source], "msg": "Expected an object", "type": "type_error"}]
        )
    lookup = {str(k).casefold(): v for k, v in data.items()} if ci else dict(data)
    result: dict[str, Any] = {}
    errors: list[dict[str, Any]] = []
    for name, kind in schema.fields.items():
        key = name.casefold() if ci else name
        if key not in lookup:
            errors.append({"loc": [source, name], "msg": "Field required", "type": "missing"})
            continue
        try:
            result[name] = kind(lookup[key])
        except (TypeError, ValueError):
            errors.append(
                {"loc": [source, name], "msg": f"Invalid {kind.__name__}", "type": "type_error"}
            )
    if errors:
        raise AdapterValidationError("invalid", errors)
    return result


class TinyAdapter:
    """Stateless, so one instance can safely serve concurrent invocations.

    ``model`` is typed ``Any`` where the protocol says ``type[BaseModel]``: this backend's
    "models" are ``Schema`` objects, and ``Any`` keeps the class a structural match.
    """

    def parse_body(self, req: HttpRequest, model: Schema) -> dict[str, Any]:
        raw = req.get_body()
        if not raw:
            raise AdapterValidationError(
                "missing body", [{"loc": ["body"], "msg": "Field required", "type": "missing"}]
            )
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MalformedRequestError("Invalid JSON") from exc
        return _check(data, model, "body")

    def parse_query(self, req: HttpRequest, model: Any) -> dict[str, Any]:
        return _check(dict(req.params or {}), model, "query")

    def parse_path(self, req: HttpRequest, model: Any) -> dict[str, Any]:
        return _check(dict(req.route_params or {}), model, "path")

    def parse_headers(self, req: HttpRequest, model: Any) -> dict[str, Any]:
        return _check(dict(req.headers or {}), model, "headers", ci=True)

    def validate_response(self, obj: Any, model: Schema, *, type_adapter: Any = None) -> Any:
        return _check(obj, model, "response")

    def serialize(self, obj: Any) -> tuple[str | bytes, str]:
        if isinstance(obj, bytes):
            return obj, "application/octet-stream"
        if isinstance(obj, str):
            return obj, "text/plain; charset=utf-8"
        converters: tuple[tuple[Callable[[Any], bool], Callable[[Any], Any]], ...] = (
            (lambda o: hasattr(o, "model_dump"), lambda o: o.model_dump()),
            (lambda o: is_dataclass(o) and not isinstance(o, type), asdict),
        )
        for matches, convert in converters:
            if matches(obj):
                obj = convert(obj)
                break
        if not isinstance(obj, (dict, list, int, float, bool)):
            raise SerializationError(type(obj).__name__)
        return json.dumps(obj), _JSON

    def serialize_response(
        self,
        obj: Any,
        model: Schema,
        *,
        type_adapter: Any = None,
        by_alias: bool = True,
        exclude_none: bool = False,
        exclude_unset: bool = False,
    ) -> tuple[str | bytes, str]:
        # Serialize strictly by the DECLARED model: keep only its fields, so extras never leak.
        return json.dumps({name: obj[name] for name in model.fields}), _JSON

    def format_error(self, exc: Exception) -> dict[str, Any]:
        errors = getattr(exc, "errors", None)
        detail = (
            errors if isinstance(errors, list) else [{"loc": [], "msg": str(exc), "type": "error"}]
        )
        return {"detail": detail}
```

## Success: run the shipped suite

Subclass `AdapterConformanceTests`, return your adapter from `make_adapter()` and override the model
hooks for a non-Pydantic backend. pytest collects every inherited `test_*` method:

```python
from azure_functions_validation.testing import AdapterConformanceTests


class TestTinyAdapterConformance(AdapterConformanceTests):
    def make_adapter(self) -> TinyAdapter:
        return TinyAdapter()

    def body_model(self) -> Schema:
        return Schema({"name": str, "count": int})

    # query_model, path_model, headers_model and response_model are overridden the same way.
```

## Failure: the suite catches contract violations

`tests/test_custom_adapter_example.py` also runs deliberately broken adapters through the same suite
and asserts that it fails:

| Broken adapter | Failing inherited test | Failure |
| --- | --- | --- |
| no `serialize_response()` (a pre-upgrade adapter) | `test_serialize_response_for_declared_model` | `AttributeError` |
| query errors without the leading `query` in `loc` | `test_query_parsing_and_error_location` | `AssertionError` |
| malformed JSON raises `ValueError` instead of `MalformedRequestError` | `test_invalid_json_raises_malformed_request_error` | `AssertionError` |

## Run it offline

No Azure account, credentials, or Functions host is needed. From the repository root:

```bash
python -m pytest tests/test_custom_adapter_example.py -v --no-cov
```

`--no-cov` only skips the repository-wide coverage gate, which one test file cannot meet.

## What conformance does not certify

`AdapterConformanceTests` checks the method contract on a fixed set of inputs. It does **not**
prove:

- thread safety or statelessness under concurrent invocations (the adapter instance is shared);
- behavior with your own models, or inputs beyond the suite's fixed values;
- performance, memory use or parsing limits of your backend;
- error transport, formatter precedence or other `@validate_http` behavior built on top of the
  adapter (the end-to-end test in the example file is only a smoke check);
- the Azure Functions host, worker or binding behavior.

The protocol itself is not changed by this example.
