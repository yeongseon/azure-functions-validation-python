# Azure Functions Validation

`azure-functions-validation` provides typed request parsing and response validation
for Python Azure Functions HTTP triggers.

## Goals

- FastAPI-like developer experience in Azure Functions
- Typed request parsing (body, query, path, headers)
- Response validation and serialization
- Consistent 422 validation errors

## Quick Example

```python
from pydantic import BaseModel
from azure_functions_validation import validate_http


class RequestModel(BaseModel):
    name: str


class ResponseModel(BaseModel):
    message: str


@validate_http(body=RequestModel, response_model=ResponseModel)
def main(body: RequestModel) -> ResponseModel:
    return ResponseModel(message=f"Hello {body.name}")
```
