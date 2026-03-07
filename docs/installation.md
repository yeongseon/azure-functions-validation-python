# Installation

`azure-functions-validation` targets the **Azure Functions Python v2 programming model**.

## Requirements

- Python 3.10+
- `azure-functions`
- Azure Functions Python **v2** (`func.FunctionApp` with decorators)

> This package does not support the legacy `function.json`-based v1 programming model.

## From PyPI

```bash
pip install azure-functions-validation
```

Ensure your Function App dependencies include:

```text
azure-functions
azure-functions-validation
```

## Local Development

```bash
git clone https://github.com/yeongseon/azure-functions-validation.git
cd azure-functions-validation
make install
```

All project maintenance commands should go through the Makefile.
