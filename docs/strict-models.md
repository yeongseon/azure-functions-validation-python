# Strict API boundary models

`@validate_http` applies the configuration on each Pydantic model you provide.
It does not make models strict or reject unknown fields automatically.

## Pydantic defaults at the boundary

A plain `BaseModel` uses Pydantic's default lax validation and
`extra="ignore"` behavior:

- `"123"` is coerced to the integer `123`.
- `"true"` is coerced to the boolean `True`.
- An integer is **not** coerced to a string in Pydantic v2; it produces a
  `string_type` validation error.
- Fields not declared by the model are silently dropped.

For example, this model accepts the payload below and the handler receives
`count=123` and `enabled=True`; `role` is discarded:

```python
class PermissiveBody(BaseModel):
    count: int
    enabled: bool


# Accepted by PermissiveBody:
# {"count": "123", "enabled": "true", "role": "admin"}
```

This behavior is useful for compatibility-oriented APIs. It is not a closed
contract: silently dropping an unexpected field can hide client mistakes and
can enable over-posting or mass-assignment bugs if raw input is also used
outside the validated model.

## Strict JSON body model

For JSON request bodies that should preserve JSON types and reject undeclared
fields, define one reusable base model:

```python
from typing import Any

import azure.functions as func
from pydantic import BaseModel, ConfigDict

from azure_functions_validation import validate_http


class StrictApiModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class StrictBody(StrictApiModel):
    count: int
    enabled: bool


@validate_http(body=StrictBody)
def create_strict(req: func.HttpRequest, body: StrictBody) -> dict[str, Any]:
    return body.model_dump()
```

With `strict=True`, JSON strings are not accepted for integer or boolean
fields. Sending `{"count":"123","enabled":"true"}` returns exactly:

```json
{
  "detail": [
    {
      "loc": ["body", "count"],
      "msg": "Input should be a valid integer",
      "type": "int_type"
    },
    {
      "loc": ["body", "enabled"],
      "msg": "Input should be a valid boolean",
      "type": "bool_type"
    }
  ],
  "error_format_version": 1
}
```

With `extra="forbid"`, sending
`{"count":123,"enabled":true,"role":"admin"}` returns exactly:

```json
{
  "detail": [
    {
      "loc": ["body", "role"],
      "msg": "Extra inputs are not permitted",
      "type": "extra_forbidden"
    }
  ],
  "error_format_version": 1
}
```

Both responses have HTTP status `422`. The decorator prefixes Pydantic's field
location with the input source, so body errors use `loc: ["body", field]`.

## Query, path, and header models

Query parameters, route values, and headers arrive from Azure Functions as
strings. A model with `strict=True` therefore rejects an integer annotation
when the client sends `?limit=10`: Pydantic sees `"10"`, not `10`.

Use a separate model family that forbids unknown fields but keeps normal string
coercion for these sources:

```python
import azure.functions as func
from pydantic import BaseModel, ConfigDict

from azure_functions_validation import validate_http


class RequestValuesModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListQuery(RequestValuesModel):
    limit: int


class StrictListQuery(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    limit: int


@validate_http(query=ListQuery)
def list_lax(req: func.HttpRequest, query: ListQuery) -> dict[str, int]:
    return {"limit": query.limit}


@validate_http(query=StrictListQuery)
def list_strict(req: func.HttpRequest, query: StrictListQuery) -> dict[str, int]:
    return {"limit": query.limit}
```

For `?limit=10`, `list_lax` receives the integer `10`. `list_strict` returns
HTTP `422`:

```json
{
  "detail": [
    {
      "loc": ["query", "limit"],
      "msg": "Input should be a valid integer",
      "type": "int_type"
    }
  ],
  "error_format_version": 1
}
```

The same caveat applies to integer, boolean, and other non-string fields in
`path=` and `headers=` models. Reserve `strict=True` for sources whose values
retain native JSON types, normally `body=`. Apply `extra="forbid"` independently
wherever unknown keys should be rejected.

## Choosing a boundary policy

| Input source | Recommended starting policy | Reason |
| --- | --- | --- |
| JSON body | `ConfigDict(strict=True, extra="forbid")` | JSON retains number, boolean, string, array, object, and null types. |
| Query | `ConfigDict(extra="forbid")` | URL values arrive as strings and need parsing. |
| Path | `ConfigDict(extra="forbid")` | Route values arrive as strings and need parsing. |
| Headers | `ConfigDict(extra="forbid", populate_by_name=True)` | Header values arrive as strings; aliases commonly map hyphenated names. |

These are starting policies, not package-wide defaults. You can opt individual
fields into stricter behavior with Pydantic field types or validators when a
source model needs a mixed policy.
