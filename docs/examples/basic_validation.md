# Basic Validation Example

## Overview

This example demonstrates the smallest complete Azure Functions Python v2 HTTP
function app that uses `validate_http` for request body validation and typed
response serialization.

It is useful when you want to enforce an explicit schema for incoming JSON and
ensure the response payload always matches a declared model.

## What It Shows

- Full `func.FunctionApp()` setup for the Python v2 programming model
- Request body parsing into a Pydantic v2 `BaseModel`
- Response validation with `response_model`
- Automatic `422` validation responses with `{"detail": [...]}`

## Complete Example

```python
import azure.functions as func
from pydantic import BaseModel

from azure_functions_validation import validate_http


class HelloRequest(BaseModel):
    name: str


class HelloResponse(BaseModel):
    message: str


app = func.FunctionApp()


@app.function_name(name="hello_validation")
@app.route(
    route="hello_validation",
    methods=["POST"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
@validate_http(body=HelloRequest, response_model=HelloResponse)
def hello_validation(req: func.HttpRequest, body: HelloRequest) -> HelloResponse:
    return HelloResponse(message=f"Hello {body.name}")
```

## How It Works

`validate_http` wraps the handler and applies validation before your business
logic runs:

1. The decorator reads the HTTP request body and parses it as JSON.
2. The JSON payload is validated against `HelloRequest`.
3. If validation succeeds, the typed `body` argument is passed to the handler.
4. The handler returns a `HelloResponse` instance.
5. The decorator validates and serializes the response model to JSON.

If request validation fails, the handler is not executed. The decorator returns
an HTTP `422` response with a structured error body.

## Expected Responses

Successful request (`POST /api/hello_validation`):

Request body:

```json
{
  "name": "Ada"
}
```

Response (`200 OK`):

```json
{
  "message": "Hello Ada"
}
```

Validation error example with missing required field:

Request body:

```json
{}
```

Response (`422 Unprocessable Entity`):

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": [
        "body",
        "name"
      ],
      "msg": "Field required"
    }
  ]
}
```

## Smoke Coverage

This documentation page matches the smoke-tested behavior in
`examples/hello_validation`:

- valid JSON body returns `200` with typed response data
- invalid JSON body returns `422` with a validation error envelope
