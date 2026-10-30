# DESIGN.md

Design Principles for `azure-functions-validation`

## Purpose

This document defines the architectural boundaries and design principles of the project.

## Design Goals

- Provide typed request parsing and response validation for Azure Functions Python v2 handlers.
- Keep the programming model Functions-native and decorator-based.
- Make validation behavior explicit, predictable, and easy to test.
- Stay small, focused, and independently useful.

## Non-Goals

This project does not aim to:

- Become a full application framework
- Replace Azure Functions routing or hosting concepts
- Introduce hidden dependency injection or global state
- Own OpenAPI generation or documentation rendering

## Design Principles

- Validation should wrap handlers, not replace them.
- Handler inputs and outputs should remain explicit and typed.
- Error responses should be consistent and machine-readable.
- Public APIs should evolve conservatively.
- Runtime overhead should stay low and implementation details easy to remove.

## Ownership

This repository owns:

- Request parsing and validation (body, query, path, headers)
- Response model validation
- Validation error formatting (`{"detail": [...]}` envelope)
- The `PipelineConfig` that captures per-handler validation contracts

## Compatibility Policy

Explicit scalar-query declarations use `query_params` keyed by keyword-only
handler arguments. One private generated Pydantic model per handler reuses the
existing query parse slot; attribute injection preserves typed values. The model
is separate from `PipelineConfig.query` and legacy metadata. Endpoint v1 schemas
reuse the existing validation-mode parameter builder. Nonempty declarations are
Pydantic-only and mutually exclusive with model queries; no signature inference
or adapter-protocol expansion is introduced. WorkerCompat hides declared inputs
while preserving binding slots. Future outer SDK binding collisions remain an
indexing boundary, not a universal decoration-time guarantee.

- Supported Python versions: `3.11`-`3.14` (metadata declares `>=3.11,<3.15`)
- Supported runtime target: Azure Functions Python v2 programming model
- Public APIs follow semantic versioning expectations

## Change Discipline

`ResponseSpec[T]` is an inert frozen/slotted/keyword-only handler value. The
protected response-building path unwraps once, validates and serializes through
the existing adapter, then constructs one SDK response using shared transport
checks. It has no media_type and does not reparse encoded bodies. Declared-model
filtering remains the disclosure boundary. Final None overrides explicit status
to 204; 204/205/304 require None, with raw SDK responses available for intentional
empty 201/202 or 205/304. Direct SDK bypass and ordinary static status behavior
remain unchanged. WorkerCompat and endpoint emission are unchanged: metadata is
a non-exhaustive fallback description, not inferred dynamic status/header facts.

Request-validation error transport is explicitly opt-in. `ErrorResponseSpec`
is a formatter value; `ValidationErrorResponse` declares a fixed status/media
and optional Pydantic error model. Only request-schema origins are eligible,
not numeric 422 or the shared validation exception class. Transport validation
is private and serialization-independent, preserving separate cookie fields.
Error model serialization follows the declared type to filter subclass fields.
Invalid formatter output fails directly to sanitized 500 without recursion.
Fixed contracts emit endpoint v2 content maps; defaults remain v1. Dynamic
formatters omit fabricated request-error schemas. No OpenAPI runtime import or
adapter protocol expansion is involved.

- Validation semantics must be covered by regression tests.
- Error payload changes are user-facing behavior changes.
- Experimental APIs must be clearly labeled in code and docs.

## Immediate Improvement Areas

The v0.5.0 pipeline separation addressed the core structural concerns:

- ~~separate sync and async execution paths cleanly~~ → done (`run_pipeline` / `run_pipeline_async` in `pipeline.py`)
- ~~parse request inputs once per request path and reuse validated values~~ → done (`PipelineConfig` frozen dataclass)
- ~~loosen handler signature assumptions without hiding request resolution errors~~ → done (explicit `_find_request_param` in `decorator.py`)
- ~~keep documentation and examples aligned with the runtime contract~~ → done (usage.md, architecture.md, 5 smoke-tested examples)

## Next Design Tasks

- evaluate whether `PipelineConfig` fields should be exposed as a public API for tooling consumers
- keep examples and smoke tests aligned with the runtime contract

## High-Level Architecture

```mermaid
flowchart TD
    subgraph import ["Import Time"]
        DEC["@validate_http\ndecorator.py"]
        PC["PipelineConfig\npipeline.py"]
        DEC -- "builds once" --> PC
    end

    subgraph request ["Per-Request"]
        PL["run_pipeline()\nrun_pipeline_async()"]
        AD["PydanticAdapter\nadapter.py"]
        H["Handler"]
        ERR["errors.py\nformat_error_response()"]

        PL -- "parse & validate\nrequest" --> AD
        AD -- "typed args" --> PL
        PL -- "invoke" --> H
        H -- "return value" --> PL
        PL -- "validate response" --> AD
        PL -- "on error" --> ERR
    end

    PC -. "cached config" .-> PL
```

## Sources

- [Azure Functions Python developer reference](https://learn.microsoft.com/en-us/azure/azure-functions/functions-reference-python)
- [Azure Functions HTTP trigger](https://learn.microsoft.com/en-us/azure/azure-functions/functions-bindings-http-webhook-trigger)
- [Supported languages in Azure Functions](https://learn.microsoft.com/en-us/azure/azure-functions/supported-languages)

## See Also

- [azure-functions-openapi — Architecture](https://github.com/yeongseon/azure-functions-openapi) — OpenAPI spec generation
- [azure-functions-logging — Architecture](https://github.com/yeongseon/azure-functions-logging) — Structured logging with contextvars
- [azure-functions-doctor — Architecture](https://github.com/yeongseon/azure-functions-doctor) — Pre-deploy diagnostic CLI
- [azure-functions-scaffold — Architecture](https://github.com/yeongseon/azure-functions-scaffold) — Project scaffolding CLI
- [azure-functions-langgraph — Architecture](https://github.com/yeongseon/azure-functions-langgraph) — LangGraph agent deployment
