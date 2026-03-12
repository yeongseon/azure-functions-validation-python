# Query / Path / Header Example

## Overview

This example demonstrates validating HTTP data from multiple input sources in a
single Azure Functions Python v2 handler: query string parameters, URL path
segments, and HTTP headers.

Use this pattern when your endpoint behavior depends on routing values and
request metadata, not only the JSON request body.

## What It Shows

- Query validation using a dedicated Pydantic model
- Path validation from a route template such as `users/{user_id}`
- Header validation with explicit alias mapping (`x-request-id`)
- Typed response generation via `response_model`

## Complete Example

```python
import azure.functions as func
from pydantic import BaseModel, ConfigDict, Field

from azure_functions_validation import validate_http


class ProfileQuery(BaseModel):
    limit: int = Field(default=10, ge=1, le=100)
    verbose: bool = False


class ProfilePath(BaseModel):
    user_id: int = Field(ge=1)


class ProfileHeaders(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    authorization: str
    x_request_id: str = Field(alias="x-request-id")


class ProfileResponse(BaseModel):
    user_id: int
    limit: int
    view: str
    request_id: str
    token_type: str


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
    token_type = headers.authorization.split(" ", maxsplit=1)[0]
    return ProfileResponse(
        user_id=path.user_id,
        limit=query.limit,
        view=view,
        request_id=headers.x_request_id,
        token_type=token_type,
    )
```

## Parameter Sources

- `query: ProfileQuery` comes from URL query string values (for example,
  `?limit=25&verbose=true`).
- `path: ProfilePath` comes from route parameters defined in
  `@app.route(route="users/{user_id}")`.
- `headers: ProfileHeaders` comes from HTTP request headers.
- `x_request_id` maps to the `x-request-id` header using a Pydantic alias.

This split keeps each input source explicit and separately validated.

## Field Constraints

`Field` constraints define numeric rules and defaults directly in the model:

- `limit: int = Field(default=10, ge=1, le=100)` sets:
  - a default value (`10`) when the query parameter is omitted
  - a lower bound (`ge=1`)
  - an upper bound (`le=100`)
- `user_id: int = Field(ge=1)` ensures route IDs are positive integers.

If a value is out of range or wrong type, `validate_http` returns `422` with a
structured `detail` list.

## Expected Responses

Successful request:

`GET /api/users/42?limit=25&verbose=true`

Headers:

```text
authorization: Bearer abc.def.ghi
x-request-id: req-7f5c8a4a
```

Response (`200 OK`):

```json
{
  "user_id": 42,
  "limit": 25,
  "view": "detailed",
  "request_id": "req-7f5c8a4a",
  "token_type": "Bearer"
}
```

Validation error example (invalid `limit=500`):

Response (`422 Unprocessable Entity`):

```json
{
  "detail": [
    {
      "type": "less_than_equal",
      "loc": [
        "query",
        "limit"
      ],
      "msg": "Input should be less than or equal to 100"
    }
  ]
}
```
