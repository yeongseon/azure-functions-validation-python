# Writing a custom adapter

Error transport remains separate from the adapter protocol. Fixed
`ValidationErrorResponse.response_model` uses a prepared Pydantic TypeAdapter,
even with a custom adapter; no new adapter methods are required. Apply outer
logging above validation so it observes early request-schema error responses,
including final status, media type and headers, with correlation context intact.
Custom adapters with unknown default error bodies publish `{}` for a fixed
error contract without a model.

The [surface evaluation](design/adapter-surface-evaluation.md) records why the
complete public contract is retained, distinguishes shipped and test-only backends,
and identifies evidence-backed internal reductions without API loss.

`ValidationAdapter` is the public backend contract behind `validate_http`.
Use a custom implementation only when the built-in `PydanticAdapter` cannot
serve your model system.

Nonempty `query_params` is deliberately Pydantic-only: omit `adapter` or pass an
exact `PydanticAdapter` instance. Custom implementations and subclasses raise
decoration-time `TypeError` with this shorthand. Existing custom adapters with
`query=Model` or an empty/absent declaration are unchanged; the protocol gains no
new methods.

## Lifetime and concurrency

The decorator receives or creates an adapter once at decoration time. That
same instance is reused by concurrent function invocations. An adapter must
therefore be stateless or make all shared state thread-safe. Per-request state
belongs in local variables, not instance attributes.

## Method contract

All normalized errors contain exactly `loc` (a list), `msg` (a string), and
`type` (a string).

| Method | Input | Output | Required failures |
| --- | --- | --- | --- |
| `parse_body(req, model)` | `HttpRequest` and backend model/type | validated value | malformed JSON or UTF-8: `MalformedRequestError`; missing/invalid value: `AdapterValidationError`, with `loc` starting with `body` |
| `parse_query(req, model)` | request query parameters and model | validated value | validation failure: `AdapterValidationError`, with `loc` starting with `query` |
| `parse_path(req, model)` | request route parameters and model | validated value | validation failure: `AdapterValidationError`, with `loc` starting with `path` |
| `parse_headers(req, model)` | request headers and model | validated value | validation failure: `AdapterValidationError`, with `loc` starting with `headers` |
| `validate_response(obj, model, type_adapter=None)` | handler result, response model, optional cached backend validator | validated value | validation failure: `AdapterValidationError`, with `loc` starting with `response` |
| `serialize_response(obj, model, type_adapter=None, by_alias=True, exclude_none=False, exclude_unset=False)` | the object `validate_response` returned, the same response model, the same optional cached validator, serialization options | `(content, content_type)` | unsupported or failed serialization: `SerializationError` |
| `serialize(obj)` | validated handler result when **no** `response_model` is configured | `(content, content_type)`, where content is `str` or `bytes` and content type is a non-empty string | unsupported or failed serialization: `SerializationError` |
| `format_error(exc)` | exception selected by the pipeline | JSON-serializable mapping containing `detail: list` | formatter defects propagate as internal faults |

`serialize_response` and `serialize` are two separate entry points, called in
mutually exclusive cases: the pipeline calls `serialize_response` whenever
`response_model=` is configured (so serialization can honor the declared
model's schema, aliases, and exclusion options -- see #463), and falls back to
`serialize` only when no `response_model` is configured at all (an ordinary
return value with no declared contract). A backend that never configures
`response_model` may implement `serialize_response` as a thin pass-through to
`serialize`.

`PydanticAdapter.serialize_response()` dumps through the declared model's
`TypeAdapter` (the pre-built one passed via `type_adapter=` when available,
otherwise one it constructs itself), which is what keeps a response-model
subclass instance from leaking its own extra fields (#463) and keeps
`by_alias=True` the default, matching the generated `endpoint` response
schema. `type_adapter` may be `None` -- the decorator only pre-builds it when
`TypeAdapter(response_model)` succeeds at decoration time, so a
non-Pydantic-compatible `response_model` intended for a custom backend does
not fail decoration (#539); a conforming implementation that needs its own
cached validator should build and cache it independently rather than assume
this hint is always present.

`PydanticAdapter.serialize()` supports Pydantic models, dictionaries, lists,
strings, bytes, integers, floats, booleans, and dataclass instances. JSON-like
values use `application/json`, strings use `text/plain; charset=utf-8`, and
bytes use `application/octet-stream`. `None` is handled by the pipeline as a
`204 No Content` response and is not passed to `serialize()` or
`serialize_response()`.

Any exception outside this taxonomy is an adapter fault. The pipeline logs it
with traceback and returns a sanitized `500`. In particular, do not use plain
`ValueError` for malformed client input. This boundary covers every adapter
entry point, including `serialize()`/`serialize_response()` when no custom
`error_formatter` is configured and `adapter.format_error()` itself: a fault
in either falls back to the built-in sanitized `500` envelope rather than
propagating out of the decorated handler or recursing into the same failing
adapter again.

## Error and formatter ordering

`ResponseSpec` is unwrapped before `validate_response`. Its content follows these
same entry points exactly once, including declared-model filtering and exclusion
flags. Without a model, only `serialize` runs. Returned bytes and the exact media
string are preserved without decoding or reparsing an SDK body. The envelope has
no `media_type`; supplied Content-Type must match the serializer. Final None
skips serialization and overrides explicit status to 204; 204/205/304 require
None. Use a raw SDK response for an intentional empty 201/202 or 205/304.
Response faults remain 500 and are not eligible for rich request-error transport.

The pipeline classifies the adapter exception first: malformed request is
`400`, request validation is `422`, and response validation, serialization,
or an unexpected exception is `500`. A handler-level `error_formatter` then
takes precedence over `adapter.format_error`. For a `5xx`, the custom formatter
receives a sanitized `InternalServerError` unless `expose_internal_errors=True`;
without a custom formatter, server errors use the built-in sanitized envelope.
The adapter's `format_error` handles the remaining default `4xx` response.

## Run the conformance suite

The public suite has no pytest import at module import time. Pytest discovers
its inherited `test_*` methods when you subclass it in your own test module:

```python
from azure_functions_validation import AdapterConformanceTests

from my_package import MyAdapter


class TestMyAdapter(AdapterConformanceTests):
    def make_adapter(self) -> MyAdapter:
        return MyAdapter()
```

The built-in fixtures are Pydantic models. A non-Pydantic backend overrides
`body_model`, `query_model`, `path_model`, `headers_model`, `response_model`,
`valid_body`, and `valid_response` as needed. Keep the inherited tests intact;
they verify parsing, source-prefixed normalized errors, response validation,
response serialization (both `serialize` and the declared-model-aware
`serialize_response`), and JSON-serializable error formatting.

## Compatibility and versioning

The protocol methods, signatures, exception classification, normalized error
shape, serialization tuple, content-type behavior, instance-reuse guarantee,
and conformance expectations are public API. Removing a method, adding a
required method or parameter, narrowing accepted values, or changing these
semantics is breaking. Additive optional capabilities may be non-breaking.

The package follows semantic-versioning expectations, but remains pre-1.0:
an incompatible protocol change is released as a new minor version rather
than a major version. Adapter authors should pin an appropriate compatible
range and run `AdapterConformanceTests` when upgrading.

`serialize_response` (#539) is one such breaking addition: any existing
custom `ValidationAdapter` implementation must add it (a thin pass-through to
`serialize` is sufficient when `response_model=` is never configured against
that backend) before upgrading past the release that introduced it.
