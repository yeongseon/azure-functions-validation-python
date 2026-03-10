# Async Validation Example

This example shows `validate_http` wrapped around an `async def` Azure Functions Python v2 handler.

It demonstrates:

- async request handling without `asyncio.run()`
- typed body validation
- typed JSON response serialization

Expected outcomes:

- valid JSON body -> `200` typed JSON response
- invalid JSON body -> `422` structured validation error
