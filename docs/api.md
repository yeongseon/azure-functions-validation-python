# API Reference

## Decorator

### `validate_http(...)`

Main decorator for request/response validation on Azure Functions HTTP handlers.

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

## Validation Metadata

These functions describe the runtime validation contracts owned by this package.
They are intended to be consumed by documentation tooling such as `azure-functions-openapi`.

### `describe_validation_contract(...)`

Returns a combined description of request, response, and 422 error contracts.

```python
from azure_functions_validation import describe_validation_contract

contract = describe_validation_contract(
    body=CreateUserRequest,
    response_model=CreateUserResponse,
)
# contract["request"]  → request source schemas
# contract["response"] → response schema
# contract["errors"]["validation"] → 422 error schema and examples
```

### `get_request_contract_metadata(...)`

Describes the validated request sources (body, query, path, headers) with their schemas.

### `get_response_contract_metadata(response_model)`

Describes the validated response type and its schema.

### `get_validation_error_contract(request_model)`

Returns the canonical 422 error contract: status code, schema, and examples derived from the request model.

### `get_contract_schema(contract_type)`

Returns a JSON schema for any Pydantic model or generic type.

---

## OpenAPI Helpers

These functions produce OpenAPI-compatible data derived from the validation contract.
They delegate to `metadata.py` — they do **not** own the contract logic.

> **Note**: OpenAPI document generation belongs to `azure-functions-openapi`.
> These helpers exist only to make the validation contract consumable in OpenAPI format.

### `generate_422_error_schema(request_model)`

Returns the OpenAPI schema object for 422 validation error responses.

### `get_validation_error_examples(request_model)`

Returns a list of example 422 error response bodies, derived from the request model's field constraints.

---

## Error Handling

### `ResponseValidationError`

Raised when response validation fails. Can be caught with a global error handler.

### `ErrorFormatter`

Type alias for `Callable[[Exception, int], dict]`. Used with the `error_formatter` parameter of `validate_http`.

### `register_global_error_handler(exception_type, handler)`

Registers a handler for a specific exception type. The most specific matching type (by MRO) is used when multiple handlers match.

```python
from azure_functions_validation import register_global_error_handler
import azure.functions as func


def handle_auth_error(exc: Exception) -> func.HttpResponse:
    return func.HttpResponse(status_code=401, body="Unauthorized")


register_global_error_handler(PermissionError, handle_auth_error)
```

### `clear_global_error_handlers()`

Removes all registered global error handlers. Useful in tests.

---

## Contract Testing

### `contract_test(request_model, response_model)`

Decorator for validating plain handler functions in tests without an `HttpRequest`.

### `verify_contracts(function, test_data, request_model, response_model)`

Calls a plain handler with `test_data` as keyword arguments and validates the inputs and output against the provided models.

---

See the [Usage guide](usage.md) for runnable examples, and [Architecture](architecture.md) for package ownership boundaries.
