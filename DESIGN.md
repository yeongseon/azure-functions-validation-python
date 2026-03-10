# DESIGN.md

Design Principles for `azure-functions-validation`

## Purpose

This document defines the architectural boundaries and design principles of the project.

## Design Goals

- Provide typed request parsing and response validation for Azure Functions Python v2 handlers.
- Keep the programming model Functions-native and decorator-based.
- Make validation behavior explicit, predictable, and easy to test.
- Stay small enough to pair cleanly with `azure-functions-openapi`.

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

## Integration Boundaries

- OpenAPI generation belongs to `azure-functions-openapi`.
- Project diagnostics belong to `azure-functions-doctor`.
- This repository owns request parsing, validation, response validation, and validation error formatting.

## Compatibility Policy

- Minimum supported Python version: `3.10`
- Supported runtime target: Azure Functions Python v2 programming model
- Public APIs follow semantic versioning expectations

## Change Discipline

- Validation semantics must be covered by regression tests.
- Error payload changes are user-facing behavior changes.
- Experimental APIs must be clearly labeled in code and docs.

## Immediate Improvement Areas

The v0.5.0 pipeline separation addressed the core structural concerns:

- ~~separate sync and async execution paths cleanly~~ → done (`run_pipeline` / `run_pipeline_async` in `pipeline.py`)
- ~~parse request inputs once per request path and reuse validated values~~ → done (`PipelineConfig` frozen dataclass)
- ~~loosen handler signature assumptions without hiding request resolution errors~~ → done (explicit `_find_request_param` in `decorator.py`)
- keep documentation and examples aligned with the runtime contract

## OpenAPI Pairing

The package should stay small and independent, but it is intentionally designed to pair well with `azure-functions-openapi`.

That means:

- response and request model conventions should stay compatible
- validation error behavior should be easy to document
- examples should show both standalone validation and OpenAPI-aligned usage

## Contract Metadata Boundary

This repository should own runtime-facing validation metadata.

That includes:

- which request models are validated
- which response models are validated
- what validation error payload shape is produced
- what reusable schema-like metadata can be exposed from those contracts

This repository should not own:

- OpenAPI path generation
- OpenAPI operation assembly
- Swagger UI rendering

## Desired Direction

The design target is:

- `azure-functions-validation` as the source of truth for validation contracts
- `azure-functions-openapi` as the consumer that renders those contracts into OpenAPI documents

This keeps runtime semantics in one place and avoids splitting request and error
contract logic across multiple packages.

## Next Design Tasks

- define a minimal public metadata surface for validated request, response, and 422 error contracts
- keep examples and smoke tests aligned with both standalone and OpenAPI-paired usage
- document which parts of the metadata surface are intended to stay stable
- evaluate whether `PipelineConfig` fields should be exposed for tooling consumers
