# azure-functions-validation

[![Python Version](https://img.shields.io/pypi/pyversions/azure-functions-validation.svg)](https://pypi.org/project/azure-functions-validation/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Lightweight validation and serialization for Python Azure Functions HTTP triggers. Brings FastAPI-like developer experience to Azure Functions with typed request parsing and response validation.

## Features

- ✅ **Typed Request Validation** - Validate request body with Pydantic models
- ✅ **Response Validation** - Ensure responses match expected schema
- ✅ **Standard Error Responses** - Automatic 422 responses for validation errors
- ✅ **Async Support** - Works with both sync and async handlers
- ✅ **Minimal Overhead** - Lightweight decorator-based API
- ✅ **Azure Functions Native** - Works seamlessly with Python v2 programming model

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

```python
import azure.functions as func
from pydantic import BaseModel, Field
from azure_functions_validation import validate_http


class CreateUserRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    email: str = Field(..., pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    age: int = Field(..., ge=0, le=120)


class CreateUserResponse(BaseModel):
    message: str
    user_id: str


app = func.FunctionApp()


@app.function_name(name="create_user")
@app.route(route="users", methods=["POST"])
@validate_http(body=CreateUserRequest, response_model=CreateUserResponse)
def create_user(body: CreateUserRequest) -> CreateUserResponse:
    # Your business logic here
    # body is already validated and typed!
    return CreateUserResponse(
        message=f"User {body.name} created",
        user_id="12345"
    )
```

### What You Get

**Valid Request:**
```bash
curl -X POST http://localhost:7071/api/users \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice", "email": "alice@example.com", "age": 30}'
```

Response (200):
```json
{
  "message": "User Alice created",
  "user_id": "12345"
}
```

**Invalid Request:**
```bash
curl -X POST http://localhost:7071/api/users \
  -H "Content-Type: application/json" \
  -d '{"name": "", "email": "invalid-email", "age": 150}'
```

Response (422):
```json
{
  "detail": [
    {
      "loc": ["body", "name"],
      "msg": "String should have at least 1 character",
      "type": "string_too_short"
    },
    {
      "loc": ["body", "email"],
      "msg": "String should match pattern '^[\\w\\.-]+@[\\w\\.-]+\\.\\w+$'",
      "type": "value_error"
    },
    {
      "loc": ["body", "age"],
      "msg": "Input should be less than or equal to 120",
      "type": "number_too_large"
    }
  ]
}
```

## Usage Examples

### Basic Body Validation

```python
from azure_functions_validation import validate_http
from pydantic import BaseModel


class MyRequest(BaseModel):
    name: str
    count: int


@validate_http(body=MyRequest)
def handler(body: MyRequest) -> dict:
    return {"message": f"Hello {body.name}"}
```

### With Response Model

```python
class MyResponse(BaseModel):
    message: str
    timestamp: str


@validate_http(body=MyRequest, response_model=MyResponse)
def handler(body: MyRequest) -> MyResponse:
    return MyResponse(
        message=f"Hello {body.name}",
        timestamp="2024-01-24T00:00:00Z"
    )
```

### Return Dict (Validated)

```python
@validate_http(body=MyRequest, response_model=MyResponse)
def handler(body: MyRequest) -> dict:
    # Dict is validated against MyResponse schema
    return {
        "message": f"Hello {body.name}",
        "timestamp": "2024-01-24T00:00:00Z"
    }
```

### Async Handler

```python
@validate_http(body=MyRequest, response_model=MyResponse)
async def handler(body: MyRequest) -> MyResponse:
    # Async operations here
    return MyResponse(message=f"Hello {body.name}")
```

### Access Original HttpRequest

```python
from azure.functions import HttpRequest


@validate_http(request_model=MyRequest, response_model=MyResponse)
def handler(req: MyRequest, http_request: HttpRequest) -> MyResponse:
    # Access original request if needed
    user_agent = http_request.headers.get("User-Agent")
    return MyResponse(message=f"Hello {req.name} from {user_agent}")
```

### Bypass Validation with HttpResponse

```python
from azure.functions import HttpResponse


@validate_http(body=MyRequest)
def handler(body: MyRequest) -> HttpResponse:
    # Return custom HttpResponse (no validation/serialization)
    return HttpResponse(
        body='{"custom": "response"}',
        mimetype="application/json",
        status_code=201
    )
```

## Error Handling

The library provides standardized error responses:

### HTTP 400 - Bad Request
Invalid JSON in request body:
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

### HTTP 422 - Unprocessable Entity
Validation errors:
```json
{
  "detail": [
    {
      "loc": ["body", "field_name"],
      "msg": "Error description",
      "type": "error_type"
    }
  ]
}
```

Supported error types:
- `missing` - Required field missing
- `invalid_type` - Wrong data type
- `value_error` - General validation error
- `string_too_short` / `string_too_long` - String length constraints
- `number_too_small` / `number_too_large` - Number range constraints
- `json_invalid` - Invalid JSON

### HTTP 500 - Internal Server Error
Response validation errors (server-side contract violation):
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

### `validate_http`

Decorator for validating Azure Functions HTTP requests and responses.

**Parameters:**
- `body` (optional): Pydantic model for request body validation
- `request_model` (optional): Shorthand for `body` (for compatibility)
- `response_model` (optional): Pydantic model for response validation

**Returns:** Decorated function that validates input/output

**Example:**
```python
@validate_http(body=RequestModel, response_model=ResponseModel)
def handler(body: RequestModel) -> ResponseModel:
    return ResponseModel(message="ok")
```

## Integration with azure-functions-openapi

Works seamlessly with [`azure-functions-openapi`](https://github.com/yeongseon/azure-functions-openapi) for runtime validation + OpenAPI documentation:

```python
from azure_functions_openapi import openapi
from azure_functions_validation import validate_http


@openapi(
    summary="Create user",
    request_model=CreateUserRequest,
    response_model=CreateUserResponse,
    tags=["Users"],
)
@validate_http(
    request_model=CreateUserRequest,
    response_model=CreateUserResponse,
)
def create_user(req: CreateUserRequest) -> CreateUserResponse:
    return CreateUserResponse(message="ok")
```

Benefits:
- Define models once, use for both docs and validation
- Reduced drift between documentation and runtime behavior
- Type-safe API development

## Examples

See the [`examples/`](examples/) directory for complete working examples:

- [`hello_validation`](examples/hello_validation/) - Comprehensive example with multiple endpoints

## Development

### Setup

```bash
make bootstrap  # Create virtual environment
make install    # Install dependencies
```

### Testing

```bash
make test       # Run tests
make cov        # Run tests with coverage
```

### Code Quality

```bash
make lint       # Run linters
make format     # Format code
make check      # Run all checks
```

## Requirements

- Python 3.10+
- Azure Functions Core Tools 4.x
- Pydantic 2.x

## Documentation

- [PRD](docs/PRD.md) - Product Requirements Document
- [Examples](examples/) - Working examples

## License

MIT

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
