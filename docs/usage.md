# Usage

This package is intended for the **Azure Functions Python v2 programming model**.
Examples below assume a decorator-based `func.FunctionApp()` HTTP application.

## Basic Request and Response Validation

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

## Query, Path, and Header Validation

```python
import azure.functions as func
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


app = func.FunctionApp()


@app.function_name(name="get_user")
@app.route(route="users/{user_id}", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(query=QueryModel, path=PathModel, headers=HeaderModel)
def get_user(
    req: func.HttpRequest,
    query: QueryModel,
    path: PathModel,
    headers: HeaderModel,
):
    return {"ok": True, "user_id": path.user_id, "limit": query.limit}
```

## Custom Error Formatter

Custom formatters and global handlers are applied to validation errors (400/422). Unexpected exceptions are re-raised so Azure Functions runtime logging can handle them.

```python
def custom_formatter(exc: Exception, status_code: int) -> dict:
    return {
        "custom": True,
        "code": f"ERR_{status_code}",
        "message": str(exc),
    }


@validate_http(error_formatter=custom_formatter)
def handler(req):
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
