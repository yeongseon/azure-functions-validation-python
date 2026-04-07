# Azure Functions Validation

[![PyPI](https://img.shields.io/pypi/v/azure-functions-validation.svg)](https://pypi.org/project/azure-functions-validation/)
[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)](https://pypi.org/project/azure-functions-validation/)
[![CI](https://github.com/yeongseon/azure-functions-validation/actions/workflows/ci-test.yml/badge.svg)](https://github.com/yeongseon/azure-functions-validation/actions/workflows/ci-test.yml)
[![Release](https://github.com/yeongseon/azure-functions-validation/actions/workflows/publish-pypi.yml/badge.svg)](https://github.com/yeongseon/azure-functions-validation/actions/workflows/publish-pypi.yml)
[![Security Scans](https://github.com/yeongseon/azure-functions-validation/actions/workflows/security.yml/badge.svg)](https://github.com/yeongseon/azure-functions-validation/actions/workflows/security.yml)
[![codecov](https://codecov.io/gh/yeongseon/azure-functions-validation/branch/main/graph/badge.svg)](https://codecov.io/gh/yeongseon/azure-functions-validation)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://pre-commit.com/)
[![Docs](https://img.shields.io/badge/docs-gh--pages-blue)](https://yeongseon.github.io/azure-functions-validation/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Read this in: [한국어](README.ko.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

Validation and serialization for the **Azure Functions Python v2 programming model**.

---

Part of the **Azure Functions Python DX Toolkit**
→ Bring FastAPI-like developer experience to Azure Functions

## Why this exists

Azure Functions Python v2 handlers often drift into the same repeated problems:

- **Repeated manual parsing** — every handler calls `req.get_json()`, `req.params.get()`, handles `ValueError` individually
- **Inconsistent error responses** — some handlers return 400, others 422, formats vary across the project
- **Missing response contracts** — response payloads silently diverge from the intended schema
- **No type safety** — request data flows through as untyped dicts, bugs surface only at runtime

## What it does

- **Typed validation** — body, query, path, and header parameters validated via Pydantic v2
- **Automatic error responses** — invalid requests get consistent `400`/`422` JSON error bodies
- **Response model enforcement** — mismatches raise `ResponseValidationError` (HTTP 500)
- **Decorator-first API** — `@validate_http` wraps your handler, no boilerplate needed

## FastAPI comparison

| Feature | FastAPI | azure-functions-validation |
|---------|---------|---------------------------|
| Request body parsing | Built-in via type hints | `@validate_http(body=Model)` |
| Query/path/header validation | `Query()`, `Path()`, `Header()` | `@validate_http(query=Model, path=Model, headers=Model)` |
| Response model | `response_model=` | `@validate_http(response_model=Model)` |
| Validation errors | Automatic 422 | Automatic 422 with `{"detail": [...]}` |
| Error customization | Exception handlers | `ErrorFormatter` callback |

## Scope

- Azure Functions Python **v2 programming model**
- HTTP-triggered functions registered on `func.FunctionApp()`
- Pydantic v2-based request and response validation

This package does **not** target the legacy `function.json`-based v1 programming model.

## What this package does not do

This package does not own:
- API documentation and spec generation — use [`azure-functions-openapi`](https://github.com/yeongseon/azure-functions-openapi)
- Runtime exposure or graph deployment — use [`azure-functions-langgraph`](https://github.com/yeongseon/azure-functions-langgraph)
- Project scaffolding — use [`azure-functions-scaffold`](https://github.com/yeongseon/azure-functions-scaffold)

## Features

- Typed body, query, path, and header validation via `@validate_http`
- Automatic 400 / 422 responses with `{"detail": [...]}` envelope
- Response model validation — mismatches raise `ResponseValidationError` (HTTP 500)
- Custom per-handler error formatting via `ErrorFormatter`

## Installation

```bash
pip install azure-functions-validation
```

Your Azure Functions app should also include:

```text
azure-functions
azure-functions-validation
```

For local development:

```bash
git clone https://github.com/yeongseon/azure-functions-validation.git
cd azure-functions-validation
pip install -e .[dev]
```

## Quick Start

```python
import azure.functions as func
from pydantic import BaseModel

from azure_functions_validation import validate_http


class CreateUserRequest(BaseModel):
    name: str
    email: str


class CreateUserResponse(BaseModel):
    message: str
    status: str = "success"


app = func.FunctionApp()


@app.function_name(name="create_user")
@app.route(route="users", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(body=CreateUserRequest, response_model=CreateUserResponse)
def create_user(req: func.HttpRequest, body: CreateUserRequest) -> CreateUserResponse:
    return CreateUserResponse(message=f"Hello {body.name}")
```

Start the Functions host locally:

```bash
func start
```

### Verify locally and on Azure

After deploying (see [docs/deployment.md](docs/deployment.md)), the same request produces the same response in both environments.

#### Local

```bash
curl -s http://localhost:7071/api/users \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice", "email": "alice@example.com"}'
```

```json
{"message": "Hello Alice", "status": "success"}
```

#### Azure

```bash
curl -s "https://<your-app>.azurewebsites.net/api/users" \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice", "email": "alice@example.com"}'
```

```json
{"message": "Hello Alice", "status": "success"}
```
Invalid requests return the same `400` error in both environments:

#### Local

```bash
curl -s http://localhost:7071/api/users \
  -H "Content-Type: application/json" \
  -d 'not json'
```

```json
{"detail": [{"loc": [], "msg": "Invalid JSON", "type": "value_error"}]}
```

> HTTP 400

#### Azure

```bash
curl -s "https://<your-app>.azurewebsites.net/api/users" \
  -H "Content-Type: application/json" \
  -d 'not json'
```

```json
{"detail": [{"loc": [], "msg": "Invalid JSON", "type": "value_error"}]}
```

> HTTP 400

> Verified against a temporary Azure Functions deployment in koreacentral (Python 3.12, Consumption plan). Response captured and URL anonymized.

## When to use

- You have HTTP-triggered Azure Functions that accept JSON request bodies
- You want Pydantic-based validation without writing manual parsing code
- You need consistent error response formats across handlers
- You want response schema enforcement to catch contract drift

## Documentation

- Project docs live under `docs/`
- Smoke-tested examples live under `examples/`
- Product requirements: `PRD.md`
- Design principles: `DESIGN.md`

## Ecosystem

This package is part of the **Azure Functions Python DX Toolkit**.

**Design principle:** `azure-functions-validation` owns request/response validation and serialization. `azure-functions-openapi` owns API documentation and spec generation. `azure-functions-langgraph` owns LangGraph runtime exposure.

| Package | Role |
|---------|------|
| [azure-functions-langgraph](https://github.com/yeongseon/azure-functions-langgraph) | LangGraph deployment adapter for Azure Functions |
| **azure-functions-validation** | Request/response validation and serialization |
| [azure-functions-openapi](https://github.com/yeongseon/azure-functions-openapi) | OpenAPI spec generation and Swagger UI |
| [azure-functions-logging](https://github.com/yeongseon/azure-functions-logging) | Structured logging and observability |
| [azure-functions-doctor](https://github.com/yeongseon/azure-functions-doctor) | Pre-deploy diagnostic CLI |
| [azure-functions-scaffold](https://github.com/yeongseon/azure-functions-scaffold) | Project scaffolding |
| [azure-functions-durable-graph](https://github.com/yeongseon/azure-functions-durable-graph) | Manifest-first graph runtime with Durable Functions |
| [azure-functions-python-cookbook](https://github.com/yeongseon/azure-functions-python-cookbook) | Recipes and examples |


## For AI Coding Assistants

When integrating with LLM-powered coding assistants, provide these files for context:

- **`llms.txt`** — Concise index with quick start and API overview
- **`llms-full.txt`** — Expanded reference with full signatures and patterns

Reference the files at repository root:
- https://github.com/yeongseon/azure-functions-validation/blob/main/llms.txt
- https://github.com/yeongseon/azure-functions-validation/blob/main/llms-full.txt

## Disclaimer

This project is an independent community project and is not affiliated with,
endorsed by, or maintained by Microsoft.

Azure and Azure Functions are trademarks of Microsoft Corporation.

## License

MIT
