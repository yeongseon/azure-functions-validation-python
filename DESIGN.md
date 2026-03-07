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
