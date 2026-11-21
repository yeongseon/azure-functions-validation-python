# Response Field Aliases

## Overview

When creating public HTTP APIs, response payloads often need camelCase or renamed JSON keys
(e.g. `id` instead of `item_id`, or `active` instead of `is_active`) while application code
prefers snake_case Python attributes. Pydantic models achieve this using field aliases such as
`Field(alias="id")` or `Field(serialization_alias="id")`.

This recipe demonstrates how Pydantic field aliases behave in `azure-functions-validation`
under supported response serialization options. It corresponds to
`examples/response_field_aliases/function_app.py`.

## Complete Working Code

```python
"""Serialized Pydantic field aliases in HTTP responses (#673)."""

from __future__ import annotations

import azure.functions as func
from pydantic import BaseModel, Field

from azure_functions_validation import validate_http


class ItemSummaryResponse(BaseModel):
    item_id: int = Field(alias="id")
    title: str
    is_active: bool = Field(default=True, alias="active")


app = func.FunctionApp()


@app.function_name(name="get_item_summary")
@app.route(
    route="response_field_aliases/summary", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS
)
@validate_http(response_model=ItemSummaryResponse)
def get_item_summary(req: func.HttpRequest) -> ItemSummaryResponse:
    """Default: response_by_alias=True emits declared Field aliases on the wire."""
    return ItemSummaryResponse(id=1, title="Widget", active=True)


@app.function_name(name="get_item_summary_by_name")
@app.route(
    route="response_field_aliases/by-name", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS
)
@validate_http(response_model=ItemSummaryResponse, response_by_alias=False)
def get_item_summary_by_name(req: func.HttpRequest) -> ItemSummaryResponse:
    """Explicit response_by_alias=False emits Python field names instead of aliases."""
    return ItemSummaryResponse(id=1, title="Widget", active=True)
```

## Wire representation & supported settings

| Handler | Configuration | Wire JSON Body | Content-Type | Status |
| --- | --- | --- | --- | --- |
| `get_item_summary` | `response_model=ItemSummaryResponse` (default `response_by_alias=True`) | `{"id":1,"title":"Widget","active":true}` | `application/json` | `200` |
| `get_item_summary_by_name` | `response_model=ItemSummaryResponse, response_by_alias=False` | `{"item_id":1,"title":"Widget","is_active":true}` | `application/json` | `200` |

### Key behaviors

1. **Default serialization (`response_by_alias=True`)**:
   When `response_model` is configured on `@validate_http`, `response_by_alias` defaults to `True`.
   Field aliases configured with `Field(alias="...")` or `Field(serialization_alias="...")` are
   serialized to the wire JSON output. Fields without an alias retain their Python attribute names.

2. **Opting out (`response_by_alias=False`)**:
   Passing `response_by_alias=False` instructs the serializer to output Python attribute names
   (e.g. `item_id` and `is_active`) instead of the aliases.

3. **Response options require `response_model`**:
   Setting `response_by_alias=False`, `response_exclude_none=True`, or `response_exclude_unset=True`
   without declaring `response_model` raises a `ValueError` at decoration time:
   `response serialization options require response_model`.

4. **Independent from FastAPI**:
   `azure-functions-validation` is a standalone library specifically designed for Azure Functions
   Python v2 applications. It does **not** inherit or import FastAPI runtime conventions, middleware,
   or parameters (such as FastAPI's `response_model_by_alias`). All response options are explicitly
   configured through `@validate_http`.

## Run it offline

No Azure account, credentials, or Functions host is needed. From the repository root:

```bash
python -m pytest tests/test_response_field_aliases_example.py -v --no-cov
```

`--no-cov` skips the repository-wide coverage threshold when testing this single file.

## Related docs

- [CRUD API](crud_api.md) — Comprehensive multi-route CRUD example with request and response models
- [Response Overrides](response_overrides.md) — Custom per-return status codes and headers via `ResponseSpec`
- [Configuration](../configuration.md#response_model) — Full configuration options reference
- [API Reference](../api.md#validate_http) — API signature for `@validate_http`
