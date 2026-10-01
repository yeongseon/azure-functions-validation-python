# Async Validation

## Overview

This example shows how `@validate_http` works with `async def` handlers in
Azure Functions Python v2.

It corresponds to:

- `examples/async_validation/function_app.py`

The key point: validation behavior is the same as sync handlers, while handler
logic can `await` asynchronous work.

## Prerequisites

1. Python 3.10+
2. Azure Functions Python v2 app
3. Installed dependencies

!!! note "Baseline knowledge"
    If this is your first endpoint, start with
    [Basic Validation](basic_validation.md) first.

## Complete Working Code

```python
import asyncio

import azure.functions as func
from pydantic import BaseModel

from azure_functions_validation import validate_http


class AsyncGreetingRequest(BaseModel):
    name: str


class AsyncGreetingResponse(BaseModel):
    message: str
    source: str = "async"


app = func.FunctionApp()


@app.function_name(name="async_validation")
@app.route(route="async_validation", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(body=AsyncGreetingRequest, response_model=AsyncGreetingResponse)
async def async_validation(
    req: func.HttpRequest,
    body: AsyncGreetingRequest,
) -> AsyncGreetingResponse:
    await asyncio.sleep(0)
    return AsyncGreetingResponse(message=f"Hello {body.name}")
```

## Step-by-step walkthrough

### Step 1: define async-safe contract models

`AsyncGreetingRequest` and `AsyncGreetingResponse` are standard Pydantic models.
No async-specific schema type is required.

### Step 2: use the same decorator configuration

`@validate_http(body=..., response_model=...)` is identical to sync handlers.

### Step 3: write async business logic

Inside the handler you can await I/O operations:

```python
await asyncio.sleep(0)
```

In real services, this would be HTTP calls, async SDK calls, or database I/O.

### Step 4: rely on validated output

The returned object is validated against `AsyncGreetingResponse` before the
HTTP response is produced.

!!! tip "No manual loop management"
    Do not call `asyncio.run()` in handlers. Azure Functions runtime manages the
    event loop for `async def` handlers.

## Test with curl

### Valid request

```bash
curl -i -X POST http://localhost:7071/api/async_validation \
  -H "Content-Type: application/json" \
  -d '{"name":"Kai"}'
```

Expected response:

```http
HTTP/1.1 200 OK
Content-Type: application/json

{"message":"Hello Kai","source":"async"}
```

### Validation error

```bash
curl -i -X POST http://localhost:7071/api/async_validation \
  -H "Content-Type: application/json" \
  -d '{"name":123}'
```

Expected response:

```http
HTTP/1.1 422 Unprocessable Entity
Content-Type: application/json

{"detail":[{"loc":["body","name"],"msg":"Input should be a valid string","type":"string_type"}]}
```

### Invalid JSON error

```bash
curl -i -X POST http://localhost:7071/api/async_validation \
  -H "Content-Type: application/json" \
  -d '{name:"Kai"}'
```

Expected response:

```http
HTTP/1.1 400 Bad Request
Content-Type: application/json

{"detail":[{"loc":[],"msg":"Invalid JSON","type":"value_error"}]}
```

## What you learned

- `@validate_http` supports `async def` without extra config
- request/response validation semantics stay consistent in async mode
- async handlers remain ideal for I/O-bound workflows
- runtime error and validation behavior remains predictable

## Related docs

- [Usage](../usage.md)
- [Configuration](../configuration.md)
- [Troubleshooting](../troubleshooting.md)
- [Custom Error Handler Example](custom_error_handler.md)
