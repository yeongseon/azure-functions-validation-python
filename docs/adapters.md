# Writing a custom adapter

`ValidationAdapter` is the public backend contract behind `validate_http`.
Use a custom implementation only when the built-in `PydanticAdapter` cannot
serve your model system.

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
| `serialize(obj)` | validated handler result | `(content, content_type)`, where content is `str` or `bytes` and content type is a non-empty string | unsupported or failed serialization: `SerializationError` |
| `format_error(exc)` | exception selected by the pipeline | JSON-serializable mapping containing `detail: list` | formatter defects propagate as internal faults |

`PydanticAdapter.serialize()` supports Pydantic models, dictionaries, lists,
strings, bytes, integers, floats, booleans, and dataclass instances. JSON-like
values use `application/json`, strings use `text/plain; charset=utf-8`, and
bytes use `application/octet-stream`. `None` is handled by the pipeline as a
`204 No Content` response and is not passed to `serialize()`.

Any exception outside this taxonomy is an adapter fault. The pipeline logs it
with traceback and returns a sanitized `500`. In particular, do not use plain
`ValueError` for malformed client input.

## Error and formatter ordering

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
serialization, and JSON-serializable error formatting.

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
