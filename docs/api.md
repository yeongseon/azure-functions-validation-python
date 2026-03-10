# API Reference

## Public API

The package exports three symbols from `azure_functions_validation`:

```python
from azure_functions_validation import (
    validate_http,
    ErrorFormatter,
    ResponseValidationError,
)
```

---

## Decorator

### `validate_http(...)`

Main decorator for request/response validation on Azure Functions HTTP handlers.

Defined in `decorator.py`. Creates a `PipelineConfig` and delegates request-time
processing to the validation pipeline (`pipeline.py`).

**Parameters**

| Parameter | Type | Description |
|---|---|---|
| `body` | `type[BaseModel]` | Pydantic model for request body |
| `query` | `type[BaseModel]` | Pydantic model for query parameters |
| `path` | `type[BaseModel]` | Pydantic model for path parameters |
| `headers` | `type[BaseModel]` | Pydantic model for request headers |
| `request_model` | `type[BaseModel]` | Shorthand alias for `body` |
| `response_model` | `type[BaseModel] \| GenericAlias` | Pydantic model for response validation |
| `error_formatter` | `Callable[[Exception, int], dict]` | Custom per-handler error formatter |
| `adapter` | `ValidationAdapter` | Custom validation adapter (defaults to `PydanticAdapter`) |

**Validation error response shape** (HTTP 422):

```json
{
  "detail": [
    {
      "loc": ["body", "field_name"],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```

---

## Error Handling

Defined in `errors.py`.

### `ResponseValidationError`

Raised when response validation fails. Produces an HTTP 500 response with the same
`{"detail": [...]}` envelope.

### `ErrorFormatter`

Type alias for `Callable[[Exception, int], dict]`. Used with the `error_formatter` parameter of `validate_http`.

```python
from azure_functions_validation import validate_http, ErrorFormatter

def custom_formatter(exc: Exception, status_code: int) -> dict:
    return {"error": str(exc), "code": status_code}

@validate_http(body=MyModel, error_formatter=custom_formatter)
def handler(req, body):
    ...
```

### `format_error_response(...)`

Internal helper that builds an `HttpResponse` from an exception and status code.
Not part of the public API — used by the pipeline to construct error responses.

---

## Internal Modules

### `pipeline.py`

Contains the request-parsing and response-building engine:

- `PipelineConfig` — frozen dataclass holding per-handler validation config
- `run_pipeline()` — synchronous pipeline entry point
- `run_pipeline_async()` — asynchronous pipeline entry point

These are internal and not exported from the package.

### `adapter.py`

Contains the `ValidationAdapter` protocol and `PydanticAdapter` implementation.
Handles model parsing, serialization, and error formatting against Pydantic v2.

---

See the [Usage guide](usage.md) for runnable examples, and [Architecture](architecture.md) for package ownership boundaries.
