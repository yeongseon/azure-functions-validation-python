# Azure Functions Validation

Lightweight validation and serialization for Python Azure Functions HTTP triggers.
This package provides typed request parsing and response validation with a decorator-first API.

## Highlights

- Pydantic-based request/response validation
- Query/path/header parsing
- Standardized 400/422 validation responses
- Unexpected exceptions bubble to Azure Functions runtime logging
- Contract testing utilities
- Optional custom/global error handlers for validation errors

## Quick Example

```python
from pydantic import BaseModel
from azure_functions_validation import validate_http

class CreateUserRequest(BaseModel):
    name: str
    email: str

class CreateUserResponse(BaseModel):
    message: str
    status: str = "success"

@validate_http(body=CreateUserRequest, response_model=CreateUserResponse)
def main(body: CreateUserRequest) -> CreateUserResponse:
    return CreateUserResponse(message=f"Hello {body.name}")
```

See **Usage** for full examples and advanced options.
