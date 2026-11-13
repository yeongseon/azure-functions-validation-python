# Multi-Source Validation-Error Aggregation

## Overview

By default `@validate_http` is **fail-fast**: the first invalid configured source returns
the `422`. With `aggregate_validation_errors=True` it validates every configured source and
returns all errors in one `422`. This walkthrough sends a body and a query string that are
**both** invalid to two otherwise identical handlers. It does not use any custom error-response
override (the separate validation-error response configuration).
Reference: [Configuration](../configuration.md#aggregate_validation_errors) and
[Usage](../usage.md#opt-in-aggregation-across-request-sources).

It corresponds to `examples/validation_aggregation/function_app.py`.

## Complete Working Code

```python
"""Fail-fast vs opt-in aggregation of validation errors across sources (#633)."""

import azure.functions as func
from pydantic import BaseModel, Field

from azure_functions_validation import validate_http


class OrderBody(BaseModel):
    sku: str = Field(min_length=3)


class OrderQuery(BaseModel):
    quantity: int = Field(ge=1)


app = func.FunctionApp()


@app.function_name(name="order_fail_fast")
@app.route(route="aggregation/fail-fast", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(body=OrderBody, query=OrderQuery)
def order_fail_fast(req: func.HttpRequest, body: OrderBody, query: OrderQuery) -> dict[str, object]:
    """Default: the first failing source is the only one reported."""
    return {"sku": body.sku, "quantity": query.quantity}


@app.function_name(name="order_aggregated")
@app.route(route="aggregation/all", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(body=OrderBody, query=OrderQuery, aggregate_validation_errors=True)
def order_aggregated(
    req: func.HttpRequest, body: OrderBody, query: OrderQuery
) -> dict[str, object]:
    """Opt-in: one 422 lists every failing source, in body, query, path, headers order."""
    return {"sku": body.sku, "quantity": query.quantity}
```

## Results

Request: `POST` with body `{"sku": "a"}` and query `?quantity=0` (both invalid).

| Handler | Status | `detail` (`loc`, `type`), in order |
| --- | --- | --- |
| `order_fail_fast` | `422` | `["body","sku"]` `string_too_short` |
| `order_aggregated` | `422` | `["body","sku"]` `string_too_short`, then `["query","quantity"]` `greater_than_equal` |

- Order is deterministic: body, query, path, then headers. The top-level source label is the
  first `loc` element.
- With a valid body and `?quantity=0`, both handlers report only the query error.
- With an empty body `{}` and no query, aggregation reports both `missing` errors.
- Malformed JSON stays an immediate `400` in both modes and is not combined with other errors.
- The handler is never called when any error is collected.

## Run it offline

No Azure account, credentials, or Functions host is needed. From the repository root:

```bash
python -m pytest tests/test_validation_aggregation_example.py -v --no-cov
```

`--no-cov` only skips the repository-wide coverage gate, which one test file cannot meet.
The tests assert status, `loc` and `type` only, never message text.
