# Header Alias Precedence

## Overview

A header model field can accept more than one wire name with
`Field(validation_alias=AliasChoices(...))`, for example a preferred header plus a legacy
one kept during a migration. This recipe pins which header wins when a client sends both.
It is separate from the [Query/Path/Header](query_validation.md) example, which uses a single
alias.

It corresponds to `examples/header_alias_precedence/function_app.py`. The behavior is
regression-tested at the adapter level in `tests/test_adapter.py`; this page adds an
end-to-end recipe through `@validate_http`.

## Complete Working Code

```python
"""Header alias precedence with ``AliasChoices``: the first listed alias wins (#636)."""

import azure.functions as func
from pydantic import AliasChoices, BaseModel, Field

from azure_functions_validation import validate_http


class ApiKeyHeaders(BaseModel):
    # Order matters: "x-api-key" is preferred; "x-legacy-api-key" is the fallback.
    api_key: str = Field(validation_alias=AliasChoices("x-api-key", "x-legacy-api-key"))


app = func.FunctionApp()


@app.function_name(name="whoami")
@app.route(route="header_alias_precedence", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(headers=ApiKeyHeaders)
def whoami(req: func.HttpRequest, headers: ApiKeyHeaders) -> dict[str, str]:
    return {"api_key": headers.api_key}
```

## Precedence

| Request headers | `api_key` |
| --- | --- |
| `x-api-key: new` | `new` |
| `x-legacy-api-key: old` | `old` (the fallback is used when the preferred one is absent) |
| both `x-api-key: new` and `x-legacy-api-key: old` | `new` (listed order wins, not request order) |
| `X-API-KEY: NEW` and `X-Legacy-Api-Key: old` | `NEW` (header names match case-insensitively) |
| neither | `422`, `loc == ["headers", "x-api-key"]`, `type == "missing"` |

- The alias listed first in `AliasChoices` has the highest precedence, whichever order the
  client sends them in.
- A missing required field is reported at the first listed alias.
- This recipe documents existing behavior only; it does not change adapter precedence.
  `AliasPath` and non-string choices are not supported for HTTP headers.

## Run it offline

No Azure account, credentials, or Functions host is needed. From the repository root:

```bash
python -m pytest tests/test_header_alias_precedence_example.py -v --no-cov
```

`--no-cov` only skips the repository-wide coverage gate, which one test file cannot meet.
The tests assert only the normalized `loc`, `type` and the selected value, never exception text.
