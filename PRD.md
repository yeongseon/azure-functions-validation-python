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
