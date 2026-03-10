# Async Validation Example

This example shows `validate_http` wrapped around an `async def` Azure Functions Python v2 handler.

It demonstrates:

- async request handling without `asyncio.run()`
- typed body validation
- typed JSON response serialization

