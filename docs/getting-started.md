# Getting Started

This quickstart walks you from zero to a validated Azure Functions HTTP endpoint
in a few minutes.

By the end, you will have:

- request body validation with Pydantic
- response validation with `response_model`
- consistent error payloads for invalid input

!!! tip "Who this is for"
    This page is for teams using the Azure Functions Python v2 programming model
    (`func.FunctionApp()` and decorators).

## Prerequisites

Before starting, make sure you have:

1. Python 3.10 or newer.
2. An Azure Functions Python v2 app structure.
3. Dependencies installed:
   - `azure-functions`
   - `azure-functions-validation`
   - `pydantic` v2.

See [Installation](installation.md) for version details.

!!! warning "Model compatibility"
    Use Pydantic v2 models (`BaseModel`).

## Step 1: Add your first validated handler

Create or update `function_app.py` with this complete example:

```python
import azure.functions as func
from pydantic import BaseModel, EmailStr, Field

from azure_functions_validation import validate_http


class SignupBody(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr


class SignupResponse(BaseModel):
    message: str
    status: str = "created"


app = func.FunctionApp()


@app.function_name(name="signup")
@app.route(route="signup", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(body=SignupBody, response_model=SignupResponse)
def signup(req: func.HttpRequest, body: SignupBody) -> SignupResponse:
    return SignupResponse(message=f"Welcome {body.name}")
```

### Why this works

- `body=SignupBody` validates incoming JSON.
- `response_model=SignupResponse` validates output before serialization.
- The handler receives a typed `body` object.

!!! note "Decorator order"
    Place `@validate_http(...)` closest to the function definition,
    below `@app.route(...)`.

## Step 2: Run your app locally

Start your Azure Functions host as you normally do for local development.

The endpoint will be available at:

- `POST /api/signup`

## Step 3: Test with `curl` (valid request)

```bash
curl -i -X POST http://localhost:7071/api/signup \
  -H "Content-Type: application/json" \
  -d '{"name":"Ada","email":"ada@example.com"}'
```

Expected response:

```http
HTTP/1.1 200 OK
Content-Type: application/json

{"message":"Welcome Ada","status":"created"}
```

## Step 4: Test with `curl` (validation error)

Send an invalid body:

```bash
curl -i -X POST http://localhost:7071/api/signup \
  -H "Content-Type: application/json" \
  -d '{"name":"","email":"not-an-email"}'
```

Expected response:

```http
HTTP/1.1 422 Unprocessable Entity
Content-Type: application/json

{"detail":[...]}
```

Expanded shape example:

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
      "msg": "value is not a valid email address",
      "type": "value_error"
    }
  ]
}
```

!!! tip "Client integration"
    Build client-side error mapping around `detail[*].loc`, `detail[*].msg`,
    and `detail[*].type` for stable UX.

## Step 5: Understand status code behavior

- `200`: handler returned valid output.
- `400`: body contained malformed JSON.
- `422`: request validation failed.
- `500`: response validation failed or internal runtime error.

## Optional: Customize error responses

If your API has a custom error envelope, pass `error_formatter`:

```python
from typing import Any


def my_error_formatter(exc: Exception, status_code: int) -> dict[str, Any]:
    return {
        "error": {
            "code": f"VALIDATION_{status_code}",
            "message": str(exc),
        }
    }


@validate_http(body=SignupBody, response_model=SignupResponse, error_formatter=my_error_formatter)
def signup_custom(req: func.HttpRequest, body: SignupBody) -> SignupResponse:
    return SignupResponse(message=f"Welcome {body.name}")
```

## Optional: Validate query/path/headers too

`validate_http` can validate more than request body:

- `query=Model`
- `path=Model`
- `headers=Model`

See [Configuration](configuration.md) for all parameters and
[Usage](usage.md) for multi-source examples.

## Troubleshooting checkpoints

If something does not work as expected:

1. Confirm the handler first positional argument is `req` (or equivalent request object).
2. Confirm your models inherit from `pydantic.BaseModel`.
3. Confirm `@validate_http` is closest to the function definition.
4. Confirm JSON body is non-empty and valid.
5. Confirm returned data matches `response_model` exactly.

For deeper fixes, go to [Troubleshooting](troubleshooting.md).

## Next steps

- Read [Configuration](configuration.md) to tune each parameter.
- Read [Usage](usage.md) for advanced patterns.
- Explore [Basic Validation Example](examples/basic_validation.md).
- Check [API Reference](api.md) for complete signatures.
