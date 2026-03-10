# PRD - azure-functions-validation

## Overview

`azure-functions-validation` provides typed request parsing, validation, and response validation for
the Azure Functions Python v2 programming model.

It is intended for decorator-based `func.FunctionApp()` HTTP handlers that want a lightweight,
Functions-native validation layer without introducing a full web framework.

## Problem Statement

Azure Functions Python HTTP handlers often repeat the same parsing and validation logic:

- parsing JSON bodies
- extracting query, path, and header values
- validating request shapes manually
- serializing and validating response payloads inconsistently

This creates duplication, uneven error handling, and drift between intended and actual API contracts.

## Goals

- Provide a decorator-first API for request and response validation.
- Normalize validation errors into predictable response payloads.
- Support typed request sources such as body, query, path, and headers.
- Keep the package aligned with Azure Functions Python v2 and companion libraries in this ecosystem.

## Non-Goals

- Building a full web framework
- Replacing Azure Functions routing or hosting behavior
- Owning OpenAPI generation
- Supporting the legacy `function.json`-based Python v1 model

## Primary Users

- Azure Functions Python API developers
- Teams that want consistent input and output contracts
- Users pairing this package with `azure-functions-openapi`

## Core Use Cases

- Validate a JSON request body into a typed model
- Validate query, path, or header models
- Validate and serialize a typed response
- Return structured validation errors for invalid input

## Success Criteria

- Representative examples pass smoke tests in CI
- Validation error payloads remain stable across releases
- Runtime validation behavior stays aligned with tests and documentation

## Next Priorities

The next iteration of the project should focus on making `azure-functions-validation`
the primary runtime contract source for request validation, response validation,
and validation error metadata.

### Priority 1

- Keep runtime request and response validation behavior stable and well-tested
- Treat validation metadata as the source of truth for downstream documentation
- Make error formatting and 422 metadata predictable enough for reuse

### Priority 2

- Expand examples for standalone validation and async handler usage
- Strengthen the OpenAPI-aligned contract story without moving spec ownership here
- Document the validation metadata surface more explicitly

## Alignment Notes

This package should remain independently useful, but its design should stay friendly to `azure-functions-openapi` in scenarios where users want both runtime validation and contract documentation.

## Contract-Source Direction

`azure-functions-validation` should own the runtime contract for:

- validated request body, query, path, and header inputs
- validated and serialized responses
- validation error payload shape
- reusable metadata derived from request and response models

That metadata can then be consumed by documentation-oriented tooling such as
`azure-functions-openapi`, but OpenAPI document generation itself remains out of scope.

## Near-Term Product Work

The next implementation steps should focus on four areas:

1. Formalize a small validation metadata surface for request, response, and 422 error data.
2. Keep OpenAPI helper functions aligned with the runtime validation contract.
3. Expand smoke-tested examples so async and OpenAPI-aligned usage stay trustworthy.
4. Tighten docs around what the package owns versus what companion packages own.
