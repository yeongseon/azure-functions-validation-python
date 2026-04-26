# Azure Functions Validation

[![PyPI](https://img.shields.io/pypi/v/azure-functions-validation.svg)](https://pypi.org/project/azure-functions-validation/)
[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)](https://pypi.org/project/azure-functions-validation/)
[![CI](https://github.com/yeongseon/azure-functions-validation-python/actions/workflows/ci-test.yml/badge.svg)](https://github.com/yeongseon/azure-functions-validation-python/actions/workflows/ci-test.yml)
[![Release](https://github.com/yeongseon/azure-functions-validation-python/actions/workflows/publish-pypi.yml/badge.svg)](https://github.com/yeongseon/azure-functions-validation-python/actions/workflows/publish-pypi.yml)
[![Security Scans](https://github.com/yeongseon/azure-functions-validation-python/actions/workflows/security.yml/badge.svg)](https://github.com/yeongseon/azure-functions-validation-python/actions/workflows/security.yml)
[![codecov](https://codecov.io/gh/yeongseon/azure-functions-validation-python/branch/main/graph/badge.svg)](https://codecov.io/gh/yeongseon/azure-functions-validation-python)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://pre-commit.com/)
[![Docs](https://img.shields.io/badge/docs-gh--pages-blue)](https://yeongseon.github.io/azure-functions-validation-python/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

其他语言: [English](README.md) | [한국어](README.ko.md) | [日本語](README.ja.md)

为 **Azure Functions Python v2 编程模型**提供 validation 和 serialization。
该包为基于 decorator 的 `FunctionApp` HTTP 处理函数提供 typed request parsing 和 response validation。

## Why Use It

Azure Functions Python v2 处理函数经常会逐渐出现同样的问题：

- 反复调用 `req.get_json()` 并手动解析请求
- 不一致的 `400` 和 `422` validation 响应
- response payload 在不知不觉中偏离预期 schema

`azure-functions-validation` 通过紧贴 Azure Functions 编程模型的 decorator-first validation 层来解决这些问题。

## Scope

- Azure Functions Python **v2 编程模型**
- 注册在 `func.FunctionApp()` 上的 HTTP 触发函数
- 基于 Pydantic v2 的 request 与 response validation

此包不面向传统的基于 `function.json` 的 v1 编程模型。

## Features

- 通过 `@validate_http` 提供 typed body、query、path 和 header validation
- 自动返回 `{"detail": [...]}` 格式的 `400` / `422` 响应
- response model validation，若不匹配则抛出 `ResponseValidationError`（HTTP 500）
- 通过 `ErrorFormatter` 支持每个处理函数的自定义错误格式化

## Installation

```bash
pip install azure-functions-validation
```

你的 Azure Functions 应用依赖还应包含：

```text
azure-functions
azure-functions-validation
```

本地开发：

```bash
git clone https://github.com/yeongseon/azure-functions-validation-python.git
cd azure-functions-validation-python
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

## Documentation

- 项目文档位于 `docs/`
- 经过 smoke test 的示例位于 `examples/`
- 产品需求文档：`PRD.md`
- 设计原则：`DESIGN.md`

## Ecosystem

- [azure-functions-langgraph](https://github.com/yeongseon/azure-functions-langgraph) — LangGraph 部署适配器
- [azure-functions-openapi](https://github.com/yeongseon/azure-functions-openapi) — OpenAPI 与 Swagger UI
- [azure-functions-logging](https://github.com/yeongseon/azure-functions-logging) — 结构化日志
- [azure-functions-doctor](https://github.com/yeongseon/azure-functions-doctor) — 诊断 CLI
- [azure-functions-scaffold](https://github.com/yeongseon/azure-functions-scaffold) — 项目脚手架
- [azure-functions-durable-graph](https://github.com/yeongseon/azure-functions-durable-graph) — 基于 Durable Functions 的图运行时
- [azure-functions-python-cookbook](https://github.com/yeongseon/azure-functions-python-cookbook) — 食谱与示例

## Disclaimer

本项目是独立的社区项目，与 Microsoft 没有关联，也未获得 Microsoft 的认可或维护。

Azure 和 Azure Functions 是 Microsoft Corporation 的商标。

## License

MIT
