# Usage

## Basic Request/Response Validation

```python
from pydantic import BaseModel
from azure_functions_validation import validate_http

class CreateUserRequest(BaseModel):
    name: str
    email: str

class CreateUserResponse(BaseModel):
    message: str
    status: str = "success"

@validate_http(body=CreateUserRequest, response_model=CreateUserResponse)
def main(body: CreateUserRequest) -> CreateUserResponse:
    return CreateUserResponse(message=f"Hello {body.name}")
```

## Query / Path / Header Validation

```python
from pydantic import BaseModel, Field
from azure_functions_validation import validate_http

class QueryModel(BaseModel):
    limit: int = Field(ge=1, le=100, default=10)
    offset: int = Field(ge=0, default=0)

class PathModel(BaseModel):
    user_id: int = Field(ge=1)

class HeaderModel(BaseModel):
    authorization: str
    user_agent: str = Field(default="unknown")

@validate_http(query=QueryModel, path=PathModel, headers=HeaderModel)
def handler(query: QueryModel, path: PathModel, headers: HeaderModel):
    return {"ok": True}
```

## Custom Error Formatter

Custom formatters and global handlers are applied to validation errors (400/422). Unexpected exceptions are re-raised so Azure Functions logs them using the default runtime logger.


```python
def custom_formatter(exc: Exception, status_code: int) -> dict:
    return {
        "custom": True,
        "code": f"ERR_{status_code}",
        "message": str(exc),
    }

@validate_http(error_formatter=custom_formatter)
def main(body: dict):
    return {"ok": True}
```

## Global Error Handler

```python
from azure_functions_validation import register_global_error_handler

def global_handler(exc: Exception):
    return {
        "detail": [
            {"loc": ["global"], "msg": str(exc), "type": "exception"}
        ]
    }

register_global_error_handler(Exception, global_handler)
```
