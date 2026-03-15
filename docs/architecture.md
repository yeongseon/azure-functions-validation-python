# Architecture

`azure-functions-validation` is intentionally small, explicit, and composable.
The package centers on one public abstraction: a decorator that enforces request
and response contracts around Azure Functions HTTP handlers.

## Design principles

- Keep public API minimal.
- Keep runtime validation deterministic.
- Separate framework integration from validation mechanics.
- Favor typed contracts over ad-hoc request parsing.
- Avoid global mutable configuration.

!!! tip "Mental model"
    The decorator builds a pipeline once at import time and executes that
    pipeline for each request.

## High-level flow

```text
HttpRequest
  -> validate_http configuration
  -> parse request inputs (body/query/path/headers)
  -> validate against Pydantic models
  -> call handler with typed arguments
  -> validate handler output (optional response_model)
  -> serialize result to HttpResponse
```

This flow is shared by sync and async handlers.

## Module responsibilities

### `decorator.py` (public entry point)

Owns:

- `validate_http(...)` API
- import-time configuration checks
- sync/async wrapper selection
- creation of immutable pipeline configuration

Not responsible for:

- actual per-request parsing and serialization logic

### `pipeline.py` (internal execution engine)

Owns:

- `PipelineConfig` data structure
- request object resolution
- input parsing orchestration
- response validation and serialization orchestration

Primary internal entry points:

- `run_pipeline(...)`
- `run_pipeline_async(...)`

### `adapter.py` (validation backend abstraction)

Owns:

- adapter protocol shape (`ValidationAdapter`)
- default implementation (`PydanticAdapter`)
- source parsing semantics (body/query/path/headers)
- serialization and default error formatting

!!! note "Extensibility"
    The adapter abstraction exists for advanced usage. Most deployments should
    keep the default `PydanticAdapter`.

### `errors.py` (error types and formatting)

Owns:

- `ResponseValidationError`
- `ErrorFormatter` alias
- `format_error_response(...)`

Error shaping policy:

- validation/parsing errors use structured JSON payloads
- 500-level internal errors are sanitized by default unless a custom formatter
  is provided

## Package ownership boundaries

### What this package owns

| Concern | Description |
| --- | --- |
| Request extraction | Parse body/query/path/headers from `HttpRequest` |
| Runtime validation | Enforce Pydantic contracts before handler execution |
| Response enforcement | Validate outbound payloads against `response_model` |
| Error envelope policy | Emit consistent `{"detail": [...]}` validation payloads |
| Decorator semantics | Injection names and conflict rules |

### What this package does not own

- Azure Functions route registration mechanics
- Authentication and authorization
- Business/domain logic
- Data persistence
- OpenAPI specification generation or documentation rendering

## Invariants and guarantees

- `validate_http` parameters are keyword-only.
- first positional handler parameter must be request-like.
- `request_model` cannot be combined with other request source parameters.
- response model validation runs unless handler returns `HttpResponse` directly.
- custom formatter is handler-scoped.

!!! warning "Import-time failures"
    Invalid decorator configuration raises exceptions when modules are imported,
    not only at request time.

## Anti-patterns to avoid

| Anti-pattern | Why it causes problems |
| --- | --- |
| Reimplementing request parsing inside handlers | Duplicates validation logic and increases drift |
| Skipping `response_model` on public APIs | Allows accidental contract breakage |
| Coupling this package to external API documentation types | Reduces modularity and maintainability |
| Overusing custom formatters everywhere | Fragments client error handling contracts |

## Related pages

- [Usage](usage.md)
- [Configuration](configuration.md)
- [API Reference](api.md)
- [Troubleshooting](troubleshooting.md)
