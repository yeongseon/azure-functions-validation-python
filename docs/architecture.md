# Architecture

This library is intentionally small and composable.

Key ideas:

- Decorator-based validation entry points
- Pydantic v2 models for parsing and validation
- Minimal coupling to Azure Functions runtime
- No global mutable state

For design principles, see `DESIGN.md`.

## Package Ownership

`azure-functions-validation` and `azure-functions-openapi` are separate packages with complementary but distinct responsibilities. Neither should duplicate the other's logic.

### What `azure-functions-validation` owns

| Concern | Description |
|---|---|
| **Request parsing** | Body, query, path, header extraction from `HttpRequest` |
| **Request validation** | Pydantic model validation for all request sources |
| **Response validation** | Pydantic model validation and serialization for responses |
| **Error payload shape** | The `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` structure |
| **Error formatting** | Per-handler custom error formatters via `ErrorFormatter` |

The decorator's `PipelineConfig` captures the full validation contract for each
handler at decoration time.  Tooling that needs to inspect what a handler
validates can read these config fields directly.

### What `azure-functions-openapi` owns

| Concern | Description |
|---|---|
| **OpenAPI document generation** | Assembling the full OpenAPI spec |
| **Route documentation** | Documenting paths, methods, and parameters |
| **Schema presentation** | Deciding how schemas appear in the OpenAPI document |
| **Response documentation** | Documenting response codes and bodies in spec form |

### What neither package owns

- Azure Functions routing (`func.FunctionApp`, `@app.route`) — that stays with the Azure Functions SDK
- Authentication and authorization logic
- Business logic

When a user wants both runtime validation and OpenAPI documentation, the
integration point is the Pydantic models themselves:

```
azure-functions-validation (runtime)
  └── Pydantic models ──shared──▶ azure-functions-openapi (docs)
        │                               │
        │  body / query / path / headers│  reads model JSON schemas
        │  response_model               │  to build OpenAPI paths/components
        │  error payload shape          │
        └───────────────────────────────┘
```

The two packages share Pydantic models as the integration contract.
`azure-functions-validation` validates at runtime; `azure-functions-openapi`
reads model schemas to generate documentation. Neither imports the other.

### Example: using models for OpenAPI generation

```python
from pydantic import BaseModel


class CreateUserRequest(BaseModel):
    name: str
    email: str


class CreateUserResponse(BaseModel):
    message: str


# azure-functions-validation uses these models at runtime:
#   @validate_http(body=CreateUserRequest, response_model=CreateUserResponse)

# azure-functions-openapi reads their JSON schemas for docs:
#   CreateUserRequest.model_json_schema()  → request schema
#   CreateUserResponse.model_json_schema() → response schema
```

The OpenAPI package consumes model schemas directly, without reimplementing
any validation logic.

### What to avoid

| Anti-pattern | Why it is wrong |
|---|---|
| `azure-functions-openapi` re-implementing error schema logic | Duplicates the error payload contract; may drift from runtime behaviour |
| `azure-functions-validation` importing OpenAPI-specific types | Creates an unwanted coupling in the wrong direction |
| Generating validation error examples outside `errors.py` | The canonical error shape is defined in `format_error_response` |
