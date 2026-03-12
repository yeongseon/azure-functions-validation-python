# Async Validation

Use this example when you want `validate_http` on an `async def` Azure
Functions Python v2 handler.

## Overview

This example shows end-to-end request and response validation on an asynchronous
HTTP trigger function.

The validation behavior is the same as synchronous handlers, but the function
can `await` I/O-bound work without blocking the worker thread.

## What It Shows

- typed body validation on an async handler
- typed response validation and serialization
- a minimal await boundary inside the handler body
- full `FunctionApp` setup with route decorators

## Complete Example

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
@app.route(
    route="async_validation",
    methods=["POST"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
@validate_http(body=AsyncGreetingRequest, response_model=AsyncGreetingResponse)
async def async_validation(
    req: func.HttpRequest,
    body: AsyncGreetingRequest,
) -> AsyncGreetingResponse:
    await asyncio.sleep(0)
    return AsyncGreetingResponse(message=f"Hello {body.name}")
```

## Async Behavior in Azure Functions

For an `async def` handler, Azure Functions executes the coroutine and awaits it
inside the runtime integration for Python v2.

With `validate_http`:

1. The decorator validates request inputs before entering your async body.
2. Your handler runs and may `await` asynchronous operations.
3. The returned object is validated against `response_model`.
4. The validated response is serialized to JSON.

No `asyncio.run()` call is needed inside the handler; the runtime manages the
event loop integration.

## When to Use Async vs Sync Handlers

Use `async def` when the handler primarily performs I/O-bound work:

- outbound HTTP calls
- asynchronous SDK/database calls
- concurrent waits on multiple external resources

Use `def` (sync) when the handler is simple and CPU-light:

- straightforward data mapping
- basic request/response shaping
- no asynchronous dependencies

Validation semantics from `validate_http` are consistent in both cases.

## Expected Responses

Successful request (`POST /api/async_validation`):

```json
{
  "name": "Kai"
}
```

Response (`200 OK`):

```json
{
  "message": "Hello Kai",
  "source": "async"
}
```

Validation error request:

```json
{
  "name": 123
}
```

Response (`422 Unprocessable Entity`):

```json
{
  "detail": [
    {
      "type": "string_type",
      "loc": [
        "body",
        "name"
      ],
      "msg": "Input should be a valid string"
    }
  ]
}
```

## Smoke Coverage

This example is smoke-tested for:

- a valid typed response
- a structured `422` validation error on invalid input
