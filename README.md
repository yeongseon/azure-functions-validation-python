# azure-functions-validation

[![Python Version](https://img.shields.io/pypi/pyversions/azure-functions-validation.svg)](https://pypi.org/project/azure-functions-validation/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Lightweight validation and serialization for Python Azure Functions HTTP triggers.
This package provides typed request parsing and response validation with a decorator-first API.

## Installation

```bash
pip install azure-functions-validation
```

For local development:

```bash
git clone https://github.com/yeongseon/azure-functions-validation.git
cd azure-functions-validation
pip install -e .[dev]
```

## Quick Start

### Basic Request/Response Validation

```python
from pydantic import BaseModel
from azure.functions import HttpRequest, HttpResponse
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

### Query, Path, and Header Validation

```python
from pydantic import BaseModel, Field
from azure.functions import HttpRequest, HttpResponse
from azure_functions_validation import validate_http

class QueryModel(BaseModel):
    limit: int = Field(ge=1, le=100, default=10)
    offset: int = Field(ge=0, default=0)


class PathModel(BaseModel):
    user_id: int = Field(ge=1)


class HeaderModel(BaseModel):
    authorization: str
    user_agent: str = Field(default="unknown")


@validate_http(body=RequestModel, query=QueryModel, path=PathModel, headers=HeaderModel)
def handler(req: HttpRequest, body: RequestModel, query: QueryModel, 
          path: PathModel, headers: HeaderModel) -> ResponseModel:
    return ResponseModel(message=f"Hello {body.name}")
```

### Custom Error Formatter

```python
def custom_formatter(exc: Exception, status_code: int) -> dict:
    return {
        "custom": True,
        "code": f"ERR_{status_code}",
        "message": str(exc),
    }

@validate_http(body=Request, response_model=Response, error_formatter=custom_formatter)
def main(body: Request) -> Response:
    return Response(message="ok")
```

### Global Error Handler Registration

```python
from azure_functions_validation import register_global_error_handler

def global_handler(exc: Exception) -> HttpResponse:
    return HttpResponse(
        body=json.dumps({"global": True, "message": str(exc)}),
        status_code=422,
        headers={"Content-Type": "application/json"},
    )

# Register for all endpoints
register_global_error_handler(Exception, global_handler)

@validate_http(body=Request, response_model=Response)
def main(body: Request) -> Response:
    return Response(message="ok")
```

### OpenAPI Integration

```python
from azure_functions_validation import generate_422_error_schema

schema = generate_422_error_schema(MyRequestModel)
# Use with azure-functions-openapi to document 422 error responses
```

### Contract Testing

```python
from azure_functions_validation import contract_test, verify_contracts

@contract_test(request_model=Request, response_model=Response)
def handler(body: Request) -> Response:
    return Response(message="ok")

result = handler(body={"name": "Alice"})
# Returns: {"success": True, "request_valid": True, "response_valid": True}
```

## Error Responses

The library returns standardized error responses following FastAPI conventions:

### 400 Bad Request
```json
{
  "detail": [
    {
      "loc": ["body"],
      "msg": "Invalid JSON",
      "type": "json_invalid"
    }
  ]
}
```

### 422 Validation Error
```json
{
  "detail": [
    {
      "loc": ["body", "name"],
      "msg": "string_too_short",
      "type": "string_too_short"
    }
  ]
}
```

### 500 Internal Server Error
```json
{
  "detail": [
    {
      "loc": ["response"],
      "msg": "Response validation error",
      "type": "response_validation_error"
    }
  ]
}
```

## API Reference

### `@validate_http` Decorator

Parameters:
- `body`: Pydantic model class for request body validation
- `query`: Pydantic model class for query parameter validation
- `path`: Pydantic model class for path parameter validation
- `headers`: Pydantic model class for header validation
- `request_model`: Shorthand for body model only (alias for body)
- `response_model`: Pydantic model class for response validation
- `error_formatter`: Custom error formatter function
- `adapter`: Custom validation adapter instance

### Functions

- `validate_http()`: Main decorator for request/response validation
- `register_global_error_handler(exception_type, handler)`: Register global error handler
- `clear_global_error_handlers()`: Clear all registered global error handlers
- `generate_422_error_schema(model)`: Generate OpenAPI schema for 422 errors
- `get_validation_error_examples(model)`: Get example 422 error responses
- `contract_test()`: Decorator for testing handler contracts
- `verify_contracts(function, test_data, ...)`: Verify handler contracts

## Documentation

- Project docs will live under `docs/`
- PRD: `docs/PRD.md`
- Technical Design: `docs/TDD.md`

## License

MIT
