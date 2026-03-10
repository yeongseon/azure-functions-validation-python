# Async Validation

Use this example when you want `validate_http` on an `async def` Azure Functions Python v2 handler.

## What It Shows

- typed body validation on an async handler
- typed response validation and serialization
- a minimal await boundary inside the handler body

## Example Path

- `examples/async_validation`

## Key Pattern

```python
@validate_http(body=AsyncGreetingRequest, response_model=AsyncGreetingResponse)
async def async_validation(
    req: func.HttpRequest, body: AsyncGreetingRequest
) -> AsyncGreetingResponse:
    await asyncio.sleep(0)
    return AsyncGreetingResponse(message=f"Hello {body.name}")
```

## Smoke Coverage

This example is smoke-tested for:

- a valid typed response
- a structured `422` validation error on invalid input

