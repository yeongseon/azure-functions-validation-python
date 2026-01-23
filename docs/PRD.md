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
| Python | 3.9+ |
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

### v0.1
- Body + Response + 422
- docs + examples + unit tests

### v0.2
- Query/Path/Header model support
- Custom error formatter hook

### v0.3
- Deeper `azure-functions-openapi` integration (e.g., 422 schema)
- Contract testing utilities (model-based tests)

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

## 17. Glossary

| Term | Definition |
|------|------------|
| **Contract** | The expected structure of request/response payloads |
| **Typed handler** | A function that receives validated model objects instead of raw JSON |
| **422 Unprocessable Entity** | Standard HTTP status for schema validation errors |
| **Cold start** | Initial latency when a serverless function is invoked after being idle |
| **Adapter** | An abstraction layer that allows swapping validation backends |