# Opt-In Body Policies: Content Type and Size

## Overview

Two opt-in options reject bad request bodies before they are parsed:

- `require_json_content_type=True` returns `415` for a non-empty body whose media type is
  neither `application/json` nor `application/*+json` (matching ignores case and parameters
  such as `; charset=utf-8`).
- `max_body_bytes=N` returns `413` when the body is larger than `N` bytes.

This recipe puts the same model behind a relaxed (default) handler and a strict handler so the
permitted and refused requests can be compared. Reference:
[Configuration](../configuration.md#max_body_bytes) and
[`require_json_content_type`](../configuration.md#require_json_content_type).

It corresponds to `examples/body_policies/function_app.py`.

## Complete Working Code

```python
"""Opt-in JSON content-type and request-size policies, permitted vs refused (#635)."""

import azure.functions as func
from pydantic import BaseModel

from azure_functions_validation import validate_http


class Note(BaseModel):
    text: str


app = func.FunctionApp()


@app.function_name(name="note_relaxed")
@app.route(route="body_policies/relaxed", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(body=Note)
def note_relaxed(req: func.HttpRequest, body: Note) -> dict[str, str]:
    """Default: no size limit, and any Content-Type is parsed as JSON."""
    return {"text": body.text}


@app.function_name(name="note_strict")
@app.route(route="body_policies/strict", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(body=Note, require_json_content_type=True, max_body_bytes=64)
def note_strict(req: func.HttpRequest, body: Note) -> dict[str, str]:
    """Opt-in: ``415`` for a non-JSON media type, ``413`` above 64 bytes."""
    return {"text": body.text}
```

## Results

| Request to `note_strict` | Status | Error `loc`, `type` |
| --- | --- | --- |
| `application/json`, `{"text": "hello"}` | `200` | |
| `text/plain` or no `Content-Type`, non-empty body | `415` | `["headers","content-type"]`, `unsupported_media_type` |
| `application/json`, body larger than 64 bytes | `413` | `["body"]`, `payload_too_large` |
| `application/json`, body of exactly 64 bytes | `200` | |

`note_relaxed` accepts the same requests (`text/plain`, no `Content-Type`, oversized bodies): both
policies are **opt-in** and default to off, so existing endpoints keep their behavior.

!!! warning "Not a replacement for transport limits"
    These checks run inside your function, after Azure Functions has already received and
    buffered the request. `max_body_bytes` is an application contract, not protection against
    resource exhaustion. Keep ingress, WAF, API Management or host request-size limits as the
    outer boundary. See [Security](../security.md) and [Deploy to Azure](../deployment.md).

## Run it offline

No Azure account, credentials, or Functions host is needed. From the repository root:

```bash
python -m pytest tests/test_body_policies_example.py -v --no-cov
```

`--no-cov` only skips the repository-wide coverage gate, which one test file cannot meet.
The tests assert status, `loc` and `type`, not message text.
