# Basic Validation Example

## Overview

This example is the smallest useful production baseline for
`azure-functions-validation-python`.

It demonstrates request body validation and response model validation in one
HTTP endpoint using the Azure Functions Python v2 decorator model.

Source code path:

- `examples/hello_validation/function_app.py`

## Prerequisites

Before running this example, make sure you have:

1. Python 3.10+
2. Azure Functions Python v2 app structure
3. Installed dependencies (`azure-functions`, `azure-functions-validation-python`, `pydantic` v2)

!!! note "First-time setup"
    If you have not completed setup yet, follow [Quickstart](../getting-started.md)
    and [Installation](../installation.md).

## Complete Working Code

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

## Step-by-step walkthrough

### Step 1: define request schema

`HelloRequest` declares what the API accepts:

```python
class HelloRequest(BaseModel):
    name: str
```

Any request body missing `name` fails before handler logic runs.

### Step 2: define response schema

`HelloResponse` declares what the API returns:

```python
class HelloResponse(BaseModel):
    message: str
```

If handler output does not match this schema, response validation fails.

### Step 3: attach decorator

```python
@validate_http(body=HelloRequest, response_model=HelloResponse)
```

This line activates request and response contract enforcement.

### Step 4: use typed handler arguments

The handler receives validated data as `body: HelloRequest` and returns a
typed model instance.

!!! tip "Typed development flow"
    IDE autocompletion and static checks become much more useful when handler
    parameters are validated model instances.

## Test with curl

### Valid request

```bash
curl -i -X POST http://localhost:7071/api/hello_validation \
  -H "Content-Type: application/json" \
  -d '{"name":"Ada"}'
```

Expected response:

```http
HTTP/1.1 200 OK
Content-Type: application/json

{"message":"Hello Ada"}
```

### Missing required field

```bash
curl -i -X POST http://localhost:7071/api/hello_validation \
  -H "Content-Type: application/json" \
  -d '{}'
```

Expected response:

```http
HTTP/1.1 422 Unprocessable Entity
Content-Type: application/json

{"detail":[{"loc":["body","name"],"msg":"Field required","type":"missing"}]}
```

### Malformed JSON

```bash
curl -i -X POST http://localhost:7071/api/hello_validation \
  -H "Content-Type: application/json" \
  -d '{name:"Ada"}'
```

Expected response:

```http
HTTP/1.1 400 Bad Request
Content-Type: application/json

{"detail":[{"loc":[],"msg":"Invalid JSON","type":"value_error"}]}
```

!!! warning "JSON syntax"
    Property names and string values must use double quotes in JSON.

## What you learned

- How to enforce body contracts with `body=...`
- How to enforce response contracts with `response_model=...`
- Why invalid input returns structured errors consistently
- Why this pattern reduces manual parsing and repetitive checks

## Related docs

- [Usage](../usage.md)
- [Configuration](../configuration.md)
- [API Reference](../api.md)
- [Troubleshooting](../troubleshooting.md)
