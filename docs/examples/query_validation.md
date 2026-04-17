# Query / Path / Header Example

## Overview

This example demonstrates validating non-body request sources in one endpoint:

- query parameters
- route path parameters
- HTTP headers

It corresponds to:

- `examples/profile_validation/function_app.py`

This pattern is ideal for read-heavy APIs where request context comes mostly
from URL and headers rather than JSON body.

## Prerequisites

1. Python 3.10+
2. Azure Functions Python v2 project
3. Installed `azure-functions-validation-python` and dependencies

!!! note "Related baseline"
    If you are new to body validation first, read
    [Basic Validation](basic_validation.md) before this page.

## Complete Working Code

```python
import azure.functions as func
from pydantic import BaseModel, ConfigDict, Field

from azure_functions_validation import validate_http


class ProfileQuery(BaseModel):
    verbose: bool = False


class ProfilePath(BaseModel):
    user_id: int = Field(ge=1)


class ProfileHeaders(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    x_request_id: str = Field(alias="x-request-id")


class ProfileResponse(BaseModel):
    user_id: int
    view: str
    request_id: str


app = func.FunctionApp()


@app.function_name(name="get_profile")
@app.route(route="users/{user_id}", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(
    query=ProfileQuery,
    path=ProfilePath,
    headers=ProfileHeaders,
    response_model=ProfileResponse,
)
def get_profile(
    req: func.HttpRequest,
    query: ProfileQuery,
    path: ProfilePath,
    headers: ProfileHeaders,
) -> ProfileResponse:
    view = "detailed" if query.verbose else "summary"
    return ProfileResponse(
        user_id=path.user_id,
        view=view,
        request_id=headers.x_request_id,
    )
```

## Step-by-step walkthrough

### Step 1: define source-specific models

- `ProfileQuery` validates `?verbose=true` style values.
- `ProfilePath` validates route value `{user_id}`.
- `ProfileHeaders` validates `x-request-id`.

Each source has its own schema and constraints.

### Step 2: map header aliases

`x-request-id` is not a valid Python identifier, so alias mapping is used:

```python
class ProfileHeaders(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    x_request_id: str = Field(alias="x-request-id")
```

### Step 3: combine decorator parameters

```python
@validate_http(query=ProfileQuery, path=ProfilePath, headers=ProfileHeaders)
```

The decorator validates all three inputs before entering your handler logic.

### Step 4: consume typed inputs

Inside the handler you get typed objects:

- `query.verbose` as `bool`
- `path.user_id` as `int`
- `headers.x_request_id` as `str`

!!! tip "Source separation"
    Keeping each source in a dedicated model reduces accidental coupling and
    makes endpoint behavior easier to test.

## Test with curl

### Valid request

```bash
curl -i "http://localhost:7071/api/users/42?verbose=true" \
  -H "x-request-id: req-7f5c8a4a"
```

Expected response:

```http
HTTP/1.1 200 OK
Content-Type: application/json

{"user_id":42,"view":"detailed","request_id":"req-7f5c8a4a"}
```

### Invalid path parameter

```bash
curl -i "http://localhost:7071/api/users/0?verbose=true" \
  -H "x-request-id: req-7f5c8a4a"
```

Expected response:

```http
HTTP/1.1 422 Unprocessable Entity
Content-Type: application/json

{"detail":[{"loc":["path","user_id"],"msg":"Input should be greater than or equal to 1","type":"greater_than_equal"}]}
```

### Missing required header

```bash
curl -i "http://localhost:7071/api/users/42?verbose=true"
```

Expected response:

```http
HTTP/1.1 422 Unprocessable Entity
Content-Type: application/json

{"detail":[{"loc":["headers","x-request-id"],"msg":"Field required","type":"missing"}]}
```

!!! warning "Route template alignment"
    Your path model field names must match route placeholders,
    such as `{user_id}` <-> `user_id`.

## What you learned

- How to validate query, path, and headers simultaneously
- How to map headers with aliases
- How route parameter constraints produce predictable `422` errors
- How response models enforce outbound data structure

## Related docs

- [Usage](../usage.md)
- [Configuration](../configuration.md)
- [Troubleshooting](../troubleshooting.md)
- [CRUD API Example](crud_api.md)
