# TDD — Technical Design Document for azure-functions-validation

## 1. Introduction

This document provides the technical design and architecture for the `azure-functions-validation` library. It translates the requirements outlined in the [Product Requirements Document (PRD)](./PRD.md) into a concrete implementation plan. The goal is to build a robust, maintainable, and extensible validation layer for Azure Functions that offers a developer experience similar to FastAPI.

---

## 2. High-Level Architecture

The library's architecture is centered around a primary decorator (`@validate_http`) that orchestrates parsing, validation, and serialization. The core logic is decoupled via a `ValidationAdapter` interface, ensuring that the validation backend (e.g., Pydantic) is pluggable.

### Request/Response Flow

```
+---------------------------+
| Azure Functions Host      |
+-------------+-------------+
              |
              | 1. Receives func.HttpRequest
              v
+-------------+-------------+
|  @validate_http Decorator |
+-------------+-------------+
              |
              | 2. Selects ValidationAdapter (e.g., PydanticV2Adapter)
              |
              | 3. Parses & Validates Inputs (Body, Query, etc.)
              |    - On Failure: Returns 400/422 HttpResponse
              v
+-------------+-------------+
|   User's Handler Function |
| (sync or async)           |
+-------------+-------------+
              |
              | 4. Executes with typed model objects
              |
              | 5. Returns data (model, dict, etc.)
              v
+-------------+-------------+
|  @validate_http Decorator |
+-------------+-------------+
              |
              | 6. Validates & Serializes Output
              |    - On Failure: Returns 500 HttpResponse
              |
              | 7. Constructs func.HttpResponse
              v
+-------------+-------------+
| Azure Functions Host      |
+---------------------------+
```

---

## 3. Core Components

### 3.1. `@validate_http` Decorator

This is the sole entry point for developers. It serves as a controller that wires together all other components.

**File:** `src/azure_functions_validation/decorator.py`

**Implementation Details:**
- The decorator will be a factory that accepts configuration (`body`, `query`, etc.) and returns a wrapper for the user's function.
- It will use Python's `inspect.signature()` to analyze the handler's parameters. This is crucial for both parameter injection and for detecting whether the handler is sync or async (`inspect.iscoroutinefunction`).
- **Logic Flow:**
    1.  On initialization, capture model arguments (`body`, `query`, etc.) and instantiate the `PydanticV2Adapter`.
    2.  The returned wrapper function receives the `func.HttpRequest`.
    3.  **Request Validation:**
        - It calls the adapter's `parse_and_validate_*` methods for each specified input source (body, query, path, headers).
        - A `try...except` block will catch validation exceptions from the adapter.
        - On failure, it uses the adapter's `format_error` method to generate a JSON payload and returns a `func.HttpResponse` with status 400 or 422.
    4.  **Parameter Injection:**
        - The validated model objects are passed as keyword arguments to the user's handler, based on the names defined in the decorator (e.g., `body=BodyModel` maps to a `body` parameter).
        - It will support a special `http_request: func.HttpRequest` parameter to pass the original request through.
    5.  **Execution:** It `await`s the handler if it's a coroutine, otherwise calls it directly.
    6.  **Response Validation & Serialization:**
        - If the handler returns a `func.HttpResponse`, it is passed through without modification.
        - If `response_model` is defined, the handler's return value is passed to the adapter's `validate_and_serialize_response` method.
        - A `try...except` block catches response validation errors, formats a 500 error payload, and returns a `func.HttpResponse`.
        - If no `response_model` is given, it applies default serialization rules (e.g., `dict` -> JSON).
    7.  Finally, it constructs and returns the successful `func.HttpResponse` with the serialized content and appropriate `Content-Type`.

### 3.2. `ValidationAdapter` Protocol

This interface defines the contract for any validation backend, ensuring the decorator remains decoupled.

**File:** `src/azure_functions_validation/adapter.py`

```python
from typing import Any, Protocol, Type
from azure.functions import HttpRequest

class ValidationAdapter(Protocol):
    """Defines the contract for a validation and serialization backend."""

    def parse_and_validate_body(self, req: HttpRequest, model: Type[Any]) -> Any:
        ...

    def parse_and_validate_query(self, req: HttpRequest, model: Type[Any]) -> Any:
        ...

    def parse_and_validate_path(self, req: HttpRequest, model: Type[Any]) -> Any:
        ...

    def parse_and_validate_headers(self, req: HttpRequest, model: Type[Any]) -> Any:
        ...

    def validate_and_serialize_response(
        self,
        response_data: Any,
        response_model: Type[Any]
    ) -> tuple[str | bytes, str]:
        """Validates and serializes the response.

        Returns:
            A tuple of (serialized_content, content_type).
        """
        ...

    def format_validation_error(self, exc: Exception) -> dict:
        """Formats a validation exception into a standard JSON dictionary."""
        ...
```

### 3.3. `PydanticV2Adapter` Implementation

This is the concrete implementation of the adapter using `pydantic v2`.

**File:** `src/azure_functions_validation/pydantic_adapter.py`

**Implementation Details:**
- **Parsing/Validation:**
    - For each `parse_and_validate_*` method, it will extract raw data from the `HttpRequest` (e.g., `req.get_json()`, `req.params`, `req.route_params`).
    - It will then use `pydantic.TypeAdapter(model).validate_python(data)` or `.validate_json(data)` for validation.
    - This approach correctly handles both `BaseModel` subclasses and other types like `list[ItemModel]`.
- **Error Formatting:**
    - The `format_validation_error` method will catch `pydantic.ValidationError`.
    - It will iterate through `exc.errors()` and map Pydantic's error structure to the library's standard format: `{ "detail": [{ "loc": [...], "msg": "...", "type": "..." }] }`.
    - A mapping dictionary will be used to translate Pydantic error types (e.g., `string_too_short`) into the library's standard types, as defined in the PRD.
- **Response Handling:**
    - The `validate_and_serialize_response` method will use `TypeAdapter(response_model).validate_python(response_data)` to validate.
    - Serialization will be done via `TypeAdapter(response_model).dump_json(validated_data)`. The content type will be `application/json`.

---

## 4. Proposed Source Code Structure

```
.
├── src/
│   └── azure_functions_validation/
│       ├── __init__.py              # Public API: @validate_http, and exceptions
│       ├── adapter.py             # ValidationAdapter protocol definition
│       ├── decorator.py           # The @validate_http decorator implementation
│       ├── exceptions.py          # Custom exceptions (e.g., ResponseValidationError)
│       ├── models.py              # Internal models for error representation
│       └── pydantic_adapter.py    # Pydantic v2 implementation of the adapter
└── tests/
    ├── conftest.py
    ├── test_decorator.py
    ├── test_pydantic_adapter.py
    └── _test_app/                 # An Azure Function app for integration testing
        ├── function_app.py
        ├── host.json
        └── local.settings.json
```

---

## 5. Error Handling Details

The library will differentiate between client-side and server-side errors.

| Scenario | Status Code | Trigger | Response Body |
|---|---|---|---|
| Invalid JSON in request body | 400 | `req.get_json()` fails | `{"detail": [{"loc": ["body"], "msg": "Invalid JSON", "type": "json_invalid"}]}` |
| Request validation failure | 422 | Pydantic `ValidationError` on input | `{"detail": [{"loc": ["body", "field"], "msg": "...", "type": "..."}]}` |
| Response validation failure | 500 | Pydantic `ValidationError` on output | `{"detail": [{"loc": ["response"], "msg": "Response validation error", "type": "response_validation_error"}]}` |
| Unhandled exception in handler | 500 | Any other exception | Default Azure Functions error response |

---

## 6. Testing Strategy

- **Unit Tests (`pytest`):**
    - **`test_pydantic_adapter.py`**: Test the `PydanticV2Adapter` in complete isolation. Provide various data and models to assert correct validation, invalidation, error formatting, and serialization.
    - **`test_decorator.py`**: Test the decorator's logic using mock functions (sync and async) and a mock adapter. Assert correct parameter injection, `await` handling, and response bypass logic.

- **Integration Tests:**
    - The `tests/_test_app` will contain a real Azure Function app.
    - Tests will use `requests` to send HTTP requests to the running function app (`func host start`).
    - Scenarios to cover:
        - Successful validation of body, query, path, and headers.
        - Correct 422 error responses for all input types.
        - Correct 400 error for malformed JSON.
        - Verify that an invalid handler return value (vs. the response_model) triggers an HTTP 500 error.
        - Verify that a handler returning a raw HttpResponse bypasses all response validation.
        - Correct handling of both `sync` and `async` handlers.
        - Passthrough of manually created `HttpResponse` objects.

This technical design provides a clear path to implementing the features defined in the PRD while ensuring the codebase is modular and testable.
