# azure-functions-validation

[![Python Version](https://img.shields.io/pypi/pyversions/azure-functions-validation.svg)](https://pypi.org/project/azure-functions-validation/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Lightweight validation and serialization for Python Azure Functions HTTP triggers.
This package provides typed request parsing and response validation with a decorator-first API.

## Installation

```bash
pip install azure-functions-validation
```

For local development:

```bash
git clone https://github.com/yeongseon/azure-functions-validation.git
cd azure-functions-validation
pip install -e .[dev]
```

## Quick Start

```python
from pydantic import BaseModel
from azure_functions_validation import validate_http


class CreateUserRequest(BaseModel):
    name: str


class CreateUserResponse(BaseModel):
    message: str


@validate_http(body=CreateUserRequest, response_model=CreateUserResponse)
def main(body: CreateUserRequest) -> CreateUserResponse:
    return CreateUserResponse(message=f"Hello {body.name}")
```

## Documentation

- Project docs will live under `docs/`
- PRD: `docs/PRD.md`

## License

MIT
