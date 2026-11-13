# Custom Validation-Error Status and Media Type

## Overview

A short recipe comparing the **default** validation-error response with the explicit
`ValidationErrorResponse` override, for one schema-invalid request (`{}`, missing
`text`). It uses only public API. The full contract is in
[Configuration](../configuration.md#validation_error_response); for a complete RFC 9457
example with a response model, see [Custom Error Handler](custom_error_handler.md).

It corresponds to `examples/error_status_media_type/function_app.py`.

## Complete Working Code

```python
"""Default vs overridden validation-error status and media type (#632)."""

import azure.functions as func
from pydantic import BaseModel

from azure_functions_validation import (
    AdapterValidationError,
    ValidationErrorResponse,
    validate_http,
)


class Comment(BaseModel):
    text: str


app = func.FunctionApp()


@app.function_name(name="comment_default")
@app.route(route="error_status/default", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(body=Comment)
def comment_default(req: func.HttpRequest, body: Comment) -> dict[str, str]:
    """No override: a schema error is ``422`` with ``application/json``."""
    return {"text": body.text}


@app.function_name(name="comment_status_only")
@app.route(route="error_status/status", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(body=Comment, validation_error_response=ValidationErrorResponse(status_code=400))
def comment_status_only(req: func.HttpRequest, body: Comment) -> dict[str, str]:
    """Status-only override: ``400``, the default body and ``application/json``."""
    return {"text": body.text}


def problem(exc: Exception, status_code: int) -> dict[str, object]:
    """The formatter still receives the ORIGINAL classified status (``422``)."""
    errors = exc.errors if isinstance(exc, AdapterValidationError) else []
    return {"title": "Invalid request", "status": 400, "errors": errors}


@app.function_name(name="comment_problem")
@app.route(route="error_status/problem", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(
    body=Comment,
    error_formatter=problem,
    validation_error_response=ValidationErrorResponse(
        status_code=400, media_type="application/problem+json"
    ),
)
def comment_problem(req: func.HttpRequest, body: Comment) -> dict[str, str]:
    """Status and media-type override with a formatter-owned body."""
    return {"text": body.text}
```

## Resulting responses for `POST` with body `{}`

| Handler | Status | Content-Type | Body (stable fields) |
| --- | --- | --- | --- |
| `comment_default` | `422` | `application/json` | `detail[0].loc == ["body", "text"]`, `type == "missing"`, `error_format_version == 1` |
| `comment_status_only` | `400` | `application/json` | same default body |
| `comment_problem` | `400` | `application/problem+json` | `title == "Invalid request"`, `status == 400`, `errors[0].loc == ["body", "text"]` |

- Without an override, behavior is unchanged: `422` and `application/json`.
- The formatter still receives the original classified status (`422`), not the declared `400`.
- A non-default media type requires an `error_formatter`; a status-only declaration can reuse
  the default body.
- Only request-schema failures are eligible. Malformed JSON (`400`), `413`, `415` and
  response failures keep their normal status and `application/json`, as the last test shows.
- Defaults and the disclosure policy are not changed by this recipe; the tests assert status,
  Content-Type, `loc` and `type`, never Pydantic message text.

## Run it offline

No Azure account, credentials, or Functions host is needed. From the repository root:

```bash
python -m pytest tests/test_error_status_media_type_example.py -v --no-cov
```

`--no-cov` only skips the repository-wide coverage gate, which one test file cannot meet.
