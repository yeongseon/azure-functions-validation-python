# PRD — azure-functions-validation

## 1. Overview

**azure-functions-validation** is a lightweight validation and serialization layer for **Azure Functions (Python HTTP Trigger)** that brings a **FastAPI-like developer experience** without introducing a full web framework.

It provides:

- Typed **request parsing & validation** (Body / Query / Path / Headers)
- Typed **response validation & serialization**
- Standardized **validation error responses (HTTP 422)**
- Decorator-first, minimal-boilerplate DX for Azure Functions Python v2 programming model

This repository is designed to work well alongside **azure-functions-openapi**, so users can define request/response models once and reuse them for both **runtime validation** and **OpenAPI documentation**.

---

## 2. Problem Statement

Building APIs on Azure Functions (Python) often requires repetitive and inconsistent code:

1. Repeated parsing logic (`req.get_json()`, `req.params.get(...)`, headers parsing)
2. No built-in structured schema validation for request contracts
3. Inconsistent error response formats across endpoints and teams
4. No strong guarantee that handler return values match the intended response shape

As a result, developers either:
- implement custom validation per function (high duplication), or
- use a full web framework (higher overhead, different runtime assumptions)

**azure-functions-validation** aims to solve this with a minimal, composable toolkit.

---

## 3. Goals

### G1. Provide FastAPI-like DX on Azure Functions
- Developers write business logic with **typed inputs** and **typed outputs**
- Validation is performed automatically via decorators

### G2. Enforce API contracts (Input + Output)
- Validate request models (body/query/path/headers)
- Validate response models before serialization

### G3. Standardize validation errors
- Return consistent, machine-readable error payloads (HTTP 422)

### G4. Stay Functions-native
- Works with Azure Functions **Python v2 programming model**
- Supports both sync and async handlers
- Keeps dependencies and runtime overhead minimal

### G5. Integrate smoothly with `azure-functions-openapi`
- Reuse the same request/response models for docs and runtime behavior
- Reduce drift between documentation and actual runtime behavior

---

## 4. Non-Goals

- Replacing FastAPI or building a full web framework
- Implementing dependency injection, routing frameworks, ORM, etc.
- Generating OpenAPI docs inside this package  
  (OpenAPI generation remains the responsibility of **azure-functions-openapi**)
- Supporting every possible content-type (e.g., multipart/form-data) in MVP

---

## 5. Target Users

- Azure Functions (Python) developers building HTTP APIs
- Teams that need consistent request/response contracts across endpoints
- Developers wanting FastAPI-like validation in a serverless-friendly way
- Users of `azure-functions-openapi` who want runtime validation that matches documented schemas

---

## 6. Key User Stories

### US1 — Validate Request Body Automatically
As a developer, I want JSON request bodies to be parsed and validated into a typed model, so that I can focus on business logic.

### US2 — Validate Query/Path/Header Parameters
As a developer, I want query params / path params / headers to be parsed into typed models with defaults and constraints.

### US3 — Validate and Serialize Responses
As a developer, I want handler outputs to be validated against an intended response schema before returning JSON.

### US4 — Reuse Models for Runtime and OpenAPI
As a developer, I want to define models once and reuse them both for:
- runtime validation (`azure-functions-validation`)
- OpenAPI docs generation (`azure-functions-openapi`)

---

## 7. Prerequisites

### 7.1 Version Requirements

| Dependency | Version |
|------------|---------|
| Python | 3.10+ |
| Azure Functions Core Tools | 4.x |
| Pydantic | 2.x (v2 only) |
| Azure Functions Python Library | v2 programming model |

---

## 8. Proposed Features

### F1 — Typed Request Parsing
- Body(JSON) → Model
- Query → Model
- Path → Model
- Headers → Model

### F2 — Typed Response Validation & Serialization
- Supports return types:
  - model instance
  - dict/list
  - string/bytes
- If `response_model` is specified:
  - validate output
  - serialize consistently

### F3 — Standard Error Response Format

| Scenario | HTTP Status |
|----------|-------------|
| JSON parsing failure | 400 Bad Request |
| Validation failure | 422 Unprocessable Entity |
| Internal error | 500 Internal Server Error |

Standard validation error response (FastAPI-inspired):

```json
{
  "detail": [
    { "loc": ["body", "name"], "msg": "Field required", "type": "missing" }
  ]
}
```

### F4 — Decorator-first API
Developer experience should be "one decorator and done".

### F5 — Async Support
Support for `async def` handlers.

### F6 — Extensible Validation Backend
MVP starts with **Pydantic v2** (practical choice), but keeps an adapter boundary to support alternatives later.

---

## 9. API Design (Draft)

### 9.1 Minimal (Body + Response)

```python
from azure_functions_validation import validate_http

@validate_http(request_model=MyRequest, response_model=MyResponse)
def main(req: MyRequest) -> MyResponse:
    return MyResponse(message=f"Hello {req.name}")
```

Notes:
- `request_model` is a shorthand for body-only validation in v0.1.
- For clarity, `body=MyRequest` is preferred in new code, but `request_model` remains supported for parity with `azure-functions-openapi`.

### 9.2 Split Models (Body / Query / Path / Headers)

```python
from azure_functions_validation import validate_http

@validate_http(
    body=BodyModel,
    query=QueryModel,
    path=PathModel,
    headers=HeaderModel,
    response_model=ResponseModel,
)
def main(body: BodyModel, query: QueryModel, path: PathModel, headers: HeaderModel) -> ResponseModel:
    ...
```

Parameter injection rule (MVP):
- Name-based mapping only. Decorator keys must match handler argument names.
- Example: `body=BodyModel` must map to `def main(body: BodyModel, ...)`.

### 9.3 Accessing Original HttpRequest

When using `request_model`, you can still access the original `HttpRequest` by including it as a parameter:

```python
from azure.functions import HttpRequest
from azure_functions_validation import validate_http

@validate_http(request_model=MyRequest, response_model=MyResponse)
def main(req: MyRequest, http_request: HttpRequest) -> MyResponse:
    # Access original request if needed
    user_agent = http_request.headers.get("User-Agent")
    return MyResponse(message=f"Hello {req.name}")
```

### 9.4 Dict Return with Response Model Validation

```python
from azure_functions_validation import validate_http

@validate_http(request_model=MyRequest, response_model=MyResponse)
def main(req: MyRequest) -> dict:
    return {"message": "ok"}  # validated & serialized as MyResponse
```

**Behavior when validation fails:**
- If the returned dict does not match `MyResponse` schema → raises `ResponseValidationError`
- Results in HTTP 500 Internal Server Error (not 422, since this is a server-side contract violation)

### 9.5 Error Handling Behavior Matrix

All error payloads in v0.1 use the FastAPI-style `detail` array with `loc`, `msg`, and `type` fields. No additional top-level fields are added.

Allowed `type` values in v0.1 (enumerated):
- `json_invalid`
- `missing`
- `invalid_type`
- `value_error`
- `string_too_short`
- `string_too_long`
- `number_too_small`
- `number_too_large`
- `response_validation_error`

Pydantic v2 error types are mapped into this set:
- `missing` and `missing_required` -> `missing`
- `type_error.*` -> `invalid_type`
- `value_error.*` -> `value_error`
- `string_too_short` -> `string_too_short`
- `string_too_long` -> `string_too_long`
- `greater_than`/`greater_than_equal`/`too_large` -> `number_too_large`
- `less_than`/`less_than_equal`/`too_small` -> `number_too_small`
- any unmapped Pydantic type -> `value_error`

| Scenario | Status | Error Payload |
|----------|--------|---------------|
| Invalid JSON body | 400 Bad Request | `{ "detail": [{ "loc": ["body"], "msg": "Invalid JSON", "type": "json_invalid" }] }` |
| Missing JSON body with body model | 422 Unprocessable Entity | `{ "detail": [{ "loc": ["body"], "msg": "Field required", "type": "missing" }] }` |
| Input validation error | 422 Unprocessable Entity | `{ "detail": [{ "loc": ["body"], "msg": "...", "type": "..." }] }` |
| Response validation error | 500 Internal Server Error | `{ "detail": [{ "loc": ["response"], "msg": "Response validation error", "type": "response_validation_error" }] }` |
| Handler raises exception | 500 Internal Server Error | Default Functions error handling (no standard payload in v0.1) |
| Handler returns HttpResponse | Pass-through | Bypass validation and return as-is |

### 9.5.1 Implementation & Test Checklist

This checklist verifies that the error handling behaviors defined above are explicitly covered by the technical design and testing strategy outlined in the TDD.

- [x] **Invalid JSON (400 Bad Request)**:
  - **TDD Mapping:** The `PydanticV2Adapter` is designed to catch `json.JSONDecodeError` and format it as a `json_invalid` error type.
  - **Test Coverage:** The TDD's "Testing Strategy" explicitly includes a test case for "Correct 400 error for malformed JSON."

- [x] **Missing/Invalid Request Fields (422 Unprocessable Entity)**:
  - **TDD Mapping:** The `PydanticV2Adapter` maps `pydantic.ValidationError` on input to a 422 response with detailed error types (`missing`, `value_error`, etc.).
  - **Test Coverage:** The TDD's "Testing Strategy" includes a test case for "Correct 422 error responses for all input types."

- [x] **Response Validation Failure (500 Internal Server Error)**:
  - **TDD Mapping:** The design specifies that a `ResponseValidationError` will be raised and handled by the decorator, resulting in a 500 error with a `response_validation_error` type.
  - **Test Coverage:** The TDD's "Testing Strategy" now explicitly includes verifying that an invalid return value triggers an HTTP 500 error.

- [x] **`HttpResponse` Passthrough**:
  - **TDD Mapping:** The decorator's logic flow is designed to check if the handler's return value is an `HttpResponse` and, if so, return it directly without attempting validation or serialization.
  - **Test Coverage:** The TDD's "Testing Strategy" now explicitly includes verifying that a handler returning a raw `HttpResponse` bypasses validation.

### 9.6 Response Serialization Defaults

- `response_model` provided:
  - model/dict/list are validated and serialized to JSON
  - default `Content-Type`: `application/json`
- `response_model` omitted:
  - `dict`/`list` serialized to JSON, `Content-Type`: `application/json`
  - `str` serialized as-is, `Content-Type`: `text/plain; charset=utf-8`
  - `bytes` returned as-is, `Content-Type`: `application/octet-stream`
- If handler returns `HttpResponse`, no serialization or validation is applied

### 9.7 Input Model Precedence and Sources

- `request_model` is shorthand for **body model only**
- `body/query/path/headers` can be provided explicitly for split models
- `request_model` cannot be combined with `body/query/path/headers` in the same decorator (configuration error)
- Path parameters are sourced from `HttpRequest.route_params`

---

## 10. Architecture

### 10.1 Request Flow

```
HTTP Request (func.HttpRequest)
        |
        v
[validate_http decorator]
  - parse query/path/header/body
  - validate using adapter (e.g., Pydantic)
  - call user handler with typed inputs
  - validate handler output (optional)
  - serialize response
        |
        v
func.HttpResponse
```

### 10.2 Adapter Interface (Concept)

```python
class ValidationAdapter(Protocol):
    def parse_body(self, req: HttpRequest, model: type) -> Any: ...
    def parse_query(self, req: HttpRequest, model: type) -> Any: ...
    def parse_headers(self, req: HttpRequest, model: type) -> Any: ...
    def parse_path(self, req: HttpRequest, model: type) -> Any: ...

    def validate_response(self, obj: Any, model: type) -> Any: ...
    def serialize(self, obj: Any) -> tuple[str | bytes, str]: ...
    #                                      ^ content    ^ content_type
    def format_error(self, exc: Exception) -> dict: ...
```

---

## 11. Integration with azure-functions-openapi

### 11.1 Recommended Usage Pattern

```python
from azure_functions_openapi import openapi
from azure_functions_validation import validate_http

@openapi(
    summary="Create user",
    request_model=CreateUserRequest,
    response_model=CreateUserResponse,
    tags=["Users"],
)
@validate_http(
    request_model=CreateUserRequest,
    response_model=CreateUserResponse,
)
def main(req: CreateUserRequest) -> CreateUserResponse:
    return CreateUserResponse(message="ok")
```

### 11.2 Benefits

- Models defined once → used for both runtime and documentation
- Reduced mismatch between OpenAPI schema and actual runtime behavior
- Cleaner API handlers with consistent contracts

### 11.3 Future Enhancements (Optional)

- OpenAPI error schema injection for 422 responses
- Shared schema/serialization utilities to reduce duplication between the two repos

---

## 12. Competitive Analysis

### 12.1 `azure-functions-parser` (similar library)

**Position**  
Often focused on request parsing/validation (primarily input) and handler conveniences.

**Pros**
- Lightweight approach
- Solves immediate input parsing pain quickly

**Cons / Limitations (relative to our goals)**
- Can feel "input-focused" rather than full contract enforcement (input + output)
- Limited ecosystem story with `azure-functions-openapi`
- Extensibility (adapter-based backend swapping) may not be a core design goal

### 12.2 Azure official OpenAPI support (.NET-oriented)

**Pros**
- Official backing
- Solid OpenAPI/Swagger tooling experience

**Cons**
- Python Functions does not have the same level of built-in DX for validation
- Runtime contract enforcement is out of scope for OpenAPI-only tooling

### 12.3 Our Differentiation

- Runtime-first: request/response validation and consistent error formatting
- OpenAPI remains separate but integrates naturally via shared models
- Adapter boundary for future validation backends

---

## 13. MVP Scope (v0.1)

### Included
- Body(JSON) → model parsing/validation
- Response model validation/serialization
- ValidationError → 422 standard error response
- Sync/Async support
- Minimal examples for Azure Functions Python v2 programming model

### Testing Strategy
- Unit tests for all parsing and validation logic
- Integration tests with Azure Functions runtime
- Example function apps for manual verification

### Excluded (to prevent scope creep)
- multipart/form-data
- OpenAPI generation built into this package
- DI/middleware frameworks

---

## 14. Roadmap

### v0.1 ✅
- Body + Query + Path + Headers + Response + 422
- docs + examples + unit tests (60 tests, 88% coverage)

### v0.2 ✅
- Query/Path/Header model support
- Full test coverage with integration tests

### v0.3 ✅
- Custom error formatter hook
- Validation error handler registration (global, opt-in)
- Deeper `azure-functions-openapi` integration (422 schema utilities)
- Contract testing utilities (model-based tests)
- All tests passing (72 passed, 78% coverage)
- Code quality improvements

---

## 15. Success Metrics

| Metric | Measurement Method |
|--------|-------------------|
| GitHub engagement | Stars / Issues / PRs trend |
| Quickstart success | Time to first successful validation (target: < 5 min) |
| Adoption | At least 3 real adoption cases (team or personal projects) |
| User satisfaction | Positive feedback from `azure-functions-openapi` users |

---

## 16. Risks & Mitigations

### R1. Azure Functions runtime changes
- **Mitigation**: Keep a thin integration layer and strong test coverage

### R2. Validation backend lock-in
- **Mitigation**: Adapter abstraction; keep project naming backend-neutral

### R3. "Why not use FastAPI?"
- **Mitigation**: Azure Functions users want minimal overhead and serverless-native patterns

### R4. Performance impact on cold start
- **Risk**: Pydantic v2 dependency may increase cold start time
- **Mitigation**: 
  - Lazy imports where possible
  - Document expected performance characteristics
  - Provide benchmarks in documentation

### R5. Memory overhead in serverless environment
- **Risk**: Additional validation layer increases memory usage
- **Mitigation**:
  - Keep dependencies minimal
  - Profile memory usage during development
  - Document memory requirements

---

## 17. Implementation Notes (DX + Runtime)

- **Type hinting DX**: Preserve handler parameter types via generics/TypeVar so IDE autocompletion remains accurate.
- **Async support**: Detect coroutine handlers (e.g., `inspect.iscoroutinefunction`) and await them; sync handlers run directly.
- **HttpResponse bypass**: If the handler returns `func.HttpResponse`, skip validation/serialization.

---

## 18. Glossary

| Term | Definition |
|------|------------|
| **Contract** | The expected structure of request/response payloads |
| **Typed handler** | A function that receives validated model objects instead of raw JSON |
| **422 Unprocessable Entity** | Standard HTTP status for schema validation errors |
| **Cold start** | Initial latency when a serverless function is invoked after being idle |
| **Adapter** | An abstraction layer that allows swapping validation backends |
