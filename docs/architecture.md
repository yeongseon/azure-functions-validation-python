# Architecture

This library is intentionally small and composable.

Key ideas:
- Decorator-based validation entry points
- Pydantic v2 models for parsing and validation
- Minimal coupling to Azure Functions runtime
- No global mutable state

For design principles, see `DESIGN.md`.
