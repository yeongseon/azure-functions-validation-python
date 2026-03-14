# Custom Error Handler

## Overview

This example demonstrates how to override default validation error responses
using the `error_formatter` parameter of `@validate_http`.

It corresponds to:

- `examples/custom_error_handler/function_app.py`

Use this pattern when your API platform requires a custom envelope or internal
error code format.

## Prerequisites

1. Python 3.10+
2. Azure Functions Python v2 app
3. Installed dependencies

!!! note "Default behavior"
    Without a custom formatter, validation errors use the standard
    `{"detail": [...]}` structure.

## Complete Working Code

```python
import azure.functions as func
from pydantic import BaseModel

from azure_functions_validation import validate_http


class CommentRequest(BaseModel):
    text: str


def custom_error_formatter(exc: Exception, status_code: int) -> dict[str, object]:
    return {
        "error": {
            "code": f"VALIDATION_{status_code}",
            "message": str(exc),
        }
    }


app = func.FunctionApp()


@app.function_name(name="create_comment")
@app.route(route="comments", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(body=CommentRequest, error_formatter=custom_error_formatter)
def create_comment(req: func.HttpRequest, body: CommentRequest) -> dict[str, str]:
    return {"text": body.text, "status": "accepted"}
```

## Step-by-step walkthrough

### Step 1: define request model

```python
class CommentRequest(BaseModel):
    text: str
```

The decorator validates incoming JSON body against this model.

### Step 2: define formatter function

```python
def custom_error_formatter(exc: Exception, status_code: int) -> dict[str, object]:
    return {
        "error": {
            "code": f"VALIDATION_{status_code}",
            "message": str(exc),
        }
    }
```

The formatter receives:

- `exc`: the exception raised during parsing/validation
- `status_code`: intended HTTP status code (`400`, `422`, `500`)

### Step 3: wire formatter into decorator

```python
@validate_http(body=CommentRequest, error_formatter=custom_error_formatter)
```

All validation pipeline errors for this handler now use your custom payload.

!!! tip "Per-handler control"
    Custom formatting is scoped to each handler. You can keep default format for
    most endpoints and customize only selected ones.

## Test with curl

### Valid request

```bash
curl -i -X POST http://localhost:7071/api/comments \
  -H "Content-Type: application/json" \
  -d '{"text":"Looks good"}'
```

Expected response:

```http
HTTP/1.1 200 OK
Content-Type: application/json

{"text":"Looks good","status":"accepted"}
```

### Missing field request

```bash
curl -i -X POST http://localhost:7071/api/comments \
  -H "Content-Type: application/json" \
  -d '{}'
```

Expected response:

```http
HTTP/1.1 422 Unprocessable Entity
Content-Type: application/json

{"error":{"code":"VALIDATION_422","message":"1 validation error for ValidationError\ntext\n  Field required [type=missing, ...]"}}
```

### Invalid JSON request

```bash
curl -i -X POST http://localhost:7071/api/comments \
  -H "Content-Type: application/json" \
  -d '{text:"bad"}'
```

Expected response:

```http
HTTP/1.1 400 Bad Request
Content-Type: application/json

{"error":{"code":"VALIDATION_400","message":"Invalid JSON"}}
```

!!! warning "Message content"
    The exact `message` string can vary by exception details. Keep client logic
    stable by relying on your own `code` field.

## What you learned

- How to implement `ErrorFormatter` with the exact required signature
- How to enforce a custom validation error envelope
- How to preserve validation while adapting API response contracts
- Why per-handler formatter scope is useful for gradual rollout

## Related docs

- [Configuration](../configuration.md)
- [API Reference](../api.md)
- [Usage](../usage.md)
- [Troubleshooting](../troubleshooting.md)
