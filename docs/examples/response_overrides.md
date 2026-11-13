# Response Status and Header Overrides

## Overview

This recipe shows `ResponseSpec`: return a non-default success status and a custom
response header **while `response_model` validation and serialization still run**.
It corresponds to `examples/response_overrides/function_app.py`.

Use it for patterns such as `201 Created` plus `Location`, or a `202` with a
tracking header. Returning `func.HttpResponse` directly would bypass
`response_model`; `ResponseSpec` does not.

## Complete Working Code

```python
"""Per-return status and header overrides that still go through ``response_model`` (#630)."""

import azure.functions as func
from pydantic import BaseModel

from azure_functions_validation import ResponseSpec, validate_http


class ItemOut(BaseModel):
    id: int
    name: str


class ItemRecord(ItemOut):
    """A storage record with a field that must never reach the client."""

    internal_note: str


app = func.FunctionApp()


@app.function_name(name="create_item")
@app.route(route="response_overrides/items", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(response_model=ItemOut, status_code=202)
def create_item(req: func.HttpRequest) -> ResponseSpec[ItemRecord]:
    """Override the decorator status (202) with 201 and add a ``Location`` header."""
    record = ItemRecord(id=1, name="alpha", internal_note="not for clients")
    return ResponseSpec(content=record, status_code=201, headers={"Location": "/api/items/1"})


@app.function_name(name="accept_item")
@app.route(
    route="response_overrides/accepted", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS
)
@validate_http(response_model=ItemOut, status_code=202)
def accept_item(req: func.HttpRequest) -> ResponseSpec[ItemOut]:
    """Omit ``status_code``: the decorator's 202 is inherited; only a header is added."""
    return ResponseSpec(content=ItemOut(id=2, name="beta"), headers={"X-Example": "accepted"})


@app.function_name(name="broken_item")
@app.route(route="response_overrides/broken", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(response_model=ItemOut)
def broken_item(req: func.HttpRequest) -> ResponseSpec[dict[str, str]]:
    """Wrong content shape: the override does NOT bypass validation, so this is a 500."""
    return ResponseSpec(content={"id": "not-an-int"}, status_code=201)
```

## Exact behavior

| Handler | Status | Headers | Body |
| --- | --- | --- | --- |
| `create_item` | `201` | `Location: /api/items/1`, `Content-Type: application/json` | `{"id":1,"name":"alpha"}` |
| `accept_item` | `202` (inherited) | `X-Example: accepted`, `Content-Type: application/json` | `{"id":2,"name":"beta"}` |
| `broken_item` | `500` | n/a | sanitized `"Internal Server Error"` envelope |

- `create_item` returns an `ItemRecord` (a subclass with `internal_note`). The declared
  `ItemOut` model filters the extra field, so `internal_note` never reaches the client.
- Omitting `status_code` on `ResponseSpec` inherits the decorator's `status_code=`.
- Wrong content (`broken_item`) is a server-side contract failure: the response is the
  sanitized `500`, never the raw payload.
- The envelope has no `media_type`; the serializer chooses `application/json`.

## Run it offline

No Azure account, credentials, or Functions host is needed. From the repository root:

```bash
python -m pytest tests/test_response_overrides_example.py -v --no-cov
```

`--no-cov` only skips the repository-wide coverage gate, which one test file cannot meet.

## See also

- [Per-return status and headers](../usage.md#per-return-status-and-headers-without-bypassing-validation)
  for the full rules (`None` and 204/205/304, header safety, repeated `Set-Cookie`).
- [Custom adapters](../adapters.md) for how `serialize_response` participates.
