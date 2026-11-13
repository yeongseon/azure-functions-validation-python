# Scalar Query Validation (no BaseModel)

## Overview

`query_params={...}` is an **opt-in** shorthand for a few scalar or flat-list query
inputs: declare Pydantic annotations by argument name and receive validated, typed
values as keyword-only handler arguments. No query `BaseModel` is needed. This page is a
standalone recipe for it; the contract is in
[Configuration](../configuration.md#query_params) and the short form is in
[Usage](../usage.md#scalar-query-inputs-without-a-model). The combined
query/path/header example is [Query/Path/Header](query_validation.md).

It corresponds to `examples/scalar_query/function_app.py`.

## Complete Working Code

```python
"""Scalar query validation without a ``BaseModel`` (opt-in ``query_params``) (#631)."""

from datetime import date
from enum import StrEnum
from typing import Annotated

import azure.functions as func
from pydantic import Field

from azure_functions_validation import validate_http


class Color(StrEnum):
    RED = "red"
    BLUE = "blue"


app = func.FunctionApp()


@app.function_name(name="search_items")
@app.route(route="scalar_query/search", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(
    query_params={
        "page": Annotated[int, Field(ge=1)],
        "tags": list[str],
        "since": date | None,
        "color": Color,
        "size": Annotated[int, Field(alias="page-size", le=50)],
    }
)
def search_items(
    req: func.HttpRequest,
    *,
    tags: list[str],
    since: date | None = None,
    color: Color = Color.RED,
    page: int = 1,
    size: int = 10,
) -> dict[str, object]:
    return {
        "page": page,
        "tags": tags,
        "since": since.isoformat() if since else None,
        "color": color.value,
        "size": size,
    }


@app.function_name(name="undeclared_query")
@app.route(route="scalar_query/undeclared", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http()
def undeclared_query(req: func.HttpRequest) -> dict[str, str | None]:
    """No ``query_params``: nothing is validated or injected; read ``req.params`` yourself."""
    return {"page": req.params.get("page")}
```

## Behavior

| Request query | Result |
| --- | --- |
| `tags=a` | `200`; defaults injected: `page=1`, `color="red"`, `size=10` |
| `tags=a&tags=b&page=3&since=2026-01-02&color=blue&page-size=7` | `200`; `tags=["a","b"]`, `since` is a `date`, `color` an enum, `size=7` |
| `tags=a&unknown=1` | `200`; unknown keys are ignored |
| `tags=a&page=0` | `422`, `loc=["query","page"]` |
| `tags=a&page=x` | `422`, `loc=["query","page"]` |
| `tags=a&color=green` | `422`, `loc=["query","color"]` |
| `tags=a&page-size=99` | `422`, `loc=["query","page-size"]` (the alias is the wire name) |
| `tags=a&page=1&page=2` | `422`, a repeated scalar is rejected, not truncated |
| (missing `tags`) | `422`, `loc=["query","tags"]`, type `missing` |

## Opt-in behavior

- Without `query_params`, nothing is validated or injected: `undeclared_query` receives
  `?page=not-a-number` untouched.
- Only keyword-only arguments named in the mapping are injected; handler annotations are not
  inferred.
- A nonempty `query_params` cannot be combined with `query=Model`; the decorator raises
  `ValueError` at import time.
- It works only with the default Pydantic adapter.

## Run it offline

No Azure account, credentials, or Functions host is needed. From the repository root:

```bash
python -m pytest tests/test_scalar_query_example.py -v --no-cov
```

`--no-cov` only skips the repository-wide coverage gate, which one test file cannot meet.
