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
| **Validation metadata** | Structured descriptions of what a handler validates (`metadata.py`) |

The `metadata.py` module is the **canonical source** for validation contract data. Anything that wants to describe or document what a handler validates should consume these helpers rather than re-implementing the logic.

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

## Integration Pattern

When a user wants both runtime validation and OpenAPI documentation, the data flow is:

```
azure-functions-validation (runtime)
  └── metadata.py  ──exports──▶  azure-functions-openapi (docs)
        │                               │
        │  describe_validation_contract │  consumes metadata to build
        │  get_request_contract_metadata│  OpenAPI paths/components
        │  get_validation_error_contract│
        └───────────────────────────────┘
```

`azure-functions-validation` produces structured metadata about its runtime contracts. `azure-functions-openapi` consumes that metadata to generate documentation. The packages stay decoupled — validation does not import openapi, and openapi does not re-implement validation logic.

### Example: sharing metadata with openapi tooling

```python
from azure_functions_validation import describe_validation_contract
from pydantic import BaseModel


class CreateUserRequest(BaseModel):
    name: str
    email: str


class CreateUserResponse(BaseModel):
    message: str


# Produce a full contract description for use by documentation tooling
contract = describe_validation_contract(
    body=CreateUserRequest,
    response_model=CreateUserResponse,
)

# contract["request"]  → request sources with schemas
# contract["response"] → response schema
# contract["errors"]["validation"] → 422 error shape and examples
```

The OpenAPI package can consume `contract` directly, without reimplementing any validation logic.

### What to avoid

| Anti-pattern | Why it is wrong |
|---|---|
| `azure-functions-openapi` re-implementing error schema logic | Duplicates the error payload contract; may drift from runtime behaviour |
| `azure-functions-validation` importing OpenAPI-specific types | Creates an unwanted coupling in the wrong direction |
| Generating validation error examples in multiple places | The canonical source is `get_validation_error_contract` in `metadata.py` |
