# Azure Functions Validation

`azure-functions-validation` is a validation layer for the **Azure Functions Python v2 programming model**.
It is designed for HTTP-triggered handlers registered on `func.FunctionApp()` using the decorator-based model.

## Highlights

- Pydantic v2 request and response validation
- Query, path, and header parsing
- Standardized validation error responses
- Contract testing utilities
- Decorator-first integration with Azure Functions Python v2

## Example

```python
import azure.functions as func
from pydantic import BaseModel

from azure_functions_validation import validate_http


class CreateUserRequest(BaseModel):
    name: str
    email: str


class CreateUserResponse(BaseModel):
    message: str


app = func.FunctionApp()


@app.function_name(name="create_user")
@app.route(route="users", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(body=CreateUserRequest, response_model=CreateUserResponse)
def create_user(req: func.HttpRequest, body: CreateUserRequest) -> CreateUserResponse:
    return CreateUserResponse(message=f"Hello {body.name}")
```

See the Usage guide for more patterns.

## Examples

- Representative: `examples/hello_validation`
- Complex: `examples/profile_validation`
- Focused: `examples/async_validation`
- Focused: `examples/openapi_aligned_validation`
