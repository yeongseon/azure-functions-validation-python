# Configuration

Validation injects configured models by parameter name: `body`, `query`, `path`
and `headers` (`req_model` for the deprecated shorthand). A required handler
parameter annotated with a configured model but named differently, such as
`payload: Input` for `body=Input`, raises a decoration-time configuration error.
Rename it to `body`; there is no implicit injection by type. Independent Azure
binding parameters and handlers that validate without consuming a model remain
supported.

This page documents every parameter of `validate_http` and how to combine them
in production handlers.

```python
@validate_http(
    body=...,
    query=...,
    query_params=None,
    path=...,
    headers=...,
    request_model=...,
    response_model=...,
    response_by_alias=True,
    response_exclude_none=False,
    response_exclude_unset=False,
    adapter=...,
    error_formatter=...,
    validation_error_response=None,
    status_code=200,
    legacy_loc=False,
    max_body_bytes=None,
    require_json_content_type=False,
    aggregate_validation_errors=False,
)
```

## Signature overview

Public keyword-only parameters:

- `body`
- `query`
- `query_params: Mapping[str, Any] | None = None`
- `path`
- `headers`
- `request_model`
- `response_model`
- `response_by_alias` (default `True`)
- `response_exclude_none` (default `False`)
- `response_exclude_unset` (default `False`)
- `adapter`
- `error_formatter`
- `validation_error_response: ValidationErrorResponse | None = None`
- `status_code` (default `200`)
- `legacy_loc` (default `False`)
- `max_body_bytes` (default `None`)
- `require_json_content_type` (default `False`)
- `aggregate_validation_errors` (default `False`)

!!! note "Keyword-only API"
    `validate_http` parameters are keyword-only. Prefer explicit names for
    readability and maintainability.

## Parameter details

### `body`

Use `body=YourBodyModel` to validate JSON request body content.

```python
class CreateBody(BaseModel):
    name: str


@validate_http(body=CreateBody)
def create(req: func.HttpRequest, body: CreateBody) -> dict[str, str]:
    return {"name": body.name}
```

Behavior:

- Empty body -> `422` (`missing` error)
- Invalid JSON syntax -> `400`
- JSON nested deeper than 512 levels -> `400` (details under [`max_body_bytes`](#max_body_bytes))
- Invalid field values -> `422`

The model's own Pydantic configuration controls coercion and unknown fields.
Plain `BaseModel` defaults are lax coercion plus `extra="ignore"`. For a closed
JSON contract, see [Strict API boundary models](strict-models.md) for the
reusable `ConfigDict(strict=True, extra="forbid")` pattern and exact errors.

### `max_body_bytes`

Set a positive byte limit to reject oversized configured bodies with `413
Payload Too Large` before JSON decoding or custom-adapter parsing. The default
`None` preserves unlimited application-level behavior. The byte count uses
`req.get_body()`; a declared `Content-Length` above the limit can be rejected
first, but Azure Functions has already buffered the body before user code runs.

```python
@validate_http(body=CreateBody, max_body_bytes=1_048_576)
def create(req: func.HttpRequest, body: CreateBody) -> dict[str, str]:
    return {"name": body.name}
```

`max_body_bytes` is an application contract, not transport-level DoS
protection. Configure Azure Functions host and/or API Management request-size
limits as the outer enforcement boundary.

Independently of the byte limit, the default Pydantic adapter accepts at most
512 nested JSON object/array levels (the outermost container counts as one).
Deeper bodies return a sanitized `400 Invalid JSON` before model validation on
every supported Python version; brackets inside strings do not count. This
portable ceiling avoids depending on interpreter-specific parser recursion
limits. Ordinary model-validation failures remain `422`. Custom adapters own
their parsing limits.

### `require_json_content_type`

**Recommended for new public JSON endpoints:** set this option explicitly to
`True`. Existing applications keep the relaxed `False` default for compatibility;
it parses valid JSON regardless of the header, including `text/plain` or an absent
header. The relaxed default alone is not evidence of an exploitable vulnerability.

Migration: first update clients to send `application/json` (or a supported
`application/*+json` type), then opt individual routes into strict mode and test
their `415` responses. No runtime warning or default change is introduced here.
Any future default change requires a separately reviewed breaking-release
migration decision and usage evidence; it must not silently ship in a patch.

Set `require_json_content_type=True` with `body=` to reject non-empty bodies
whose media type is neither `application/json` nor `application/*+json` with
`415 Unsupported Media Type`. Matching is case-insensitive and ignores
parameters such as `; charset=utf-8`.

Empty bodies without `Content-Type` continue to the existing `422` missing-body
path. A non-empty body without `Content-Type` receives `415`. The default
`False` preserves the existing behavior of attempting JSON parsing regardless
of the header.

### `aggregate_validation_errors`

The default `False` preserves fail-fast validation: the first invalid configured
source returns a 422. Set `aggregate_validation_errors=True` to validate every
configured source and return body, query, path, and header errors together in
that deterministic order. Errors keep their source-prefixed `loc` values and
the existing `error_format_version`.

Malformed input still returns 400 immediately, and body policy or unexpected
adapter failures still return their existing immediate error response. The
handler is never called when any validation error was collected.

### `query`

Use `query=QueryModel` to validate query-string parameters.

Query values arrive as strings. Keep normal Pydantic coercion for fields such
as `page: int`; a model-wide `strict=True` rejects `?page=2`. You can still use
`ConfigDict(extra="forbid")` to reject undeclared query keys. See
[Strict API boundary models](strict-models.md).

```python
class QueryModel(BaseModel):
    page: int = Field(default=1, ge=1)


@validate_http(query=QueryModel)
def list_items(req: func.HttpRequest, query: QueryModel) -> dict[str, int]:
    return {"page": query.page}
```

### `query_params`

For a few scalar inputs, declare Pydantic annotations without a dedicated model:

```python
from typing import Annotated

from pydantic import Field


@validate_http(query_params={"page": Annotated[int, Field(ge=1)]})
def list_items(req: func.HttpRequest, *, page: int = 1) -> dict[str, int]:
    return {"page": page}
```

Mapping keys are Python argument names, each explicitly keyword-only. The
declaration controls validation; handler annotations are not inferred. A handler
default is validated and injected when input is absent. Otherwise an `Annotated`
default/default factory applies, or the input is required (even `int | None`).
Factories run per request, never while generating metadata. Defaults in both
places, or `Field(...)` as a handler default, raise `ValueError` at decoration.

Scalars, scalar unions and flat lists are supported, including dates, enums and
UUIDs as typed Python values. `list[str]` receives one value as a singleton list
and repeated keys in order. A repeated scalar is rejected, not truncated.
Scalar-or-list unions retain the existing parser's normalization. Blank input is
not missing, and `null` is not a special textual null convention. Unknown query
keys are ignored. Invalid values/defaults return normal `422` errors with
`loc=["query", wire_name]`; aggregation keeps body, query, path, headers order.

`Field(alias="page-size")` or a string `validation_alias` changes the inbound
wire name, not the injected Python name. A serialization-only alias does not
change input. Aliased fields do not also accept their Python names.
`AliasChoices`, `AliasPath`, an empty inbound name, duplicate wire aliases, and
aliases matching another declared Python name raise decoration-time `ValueError`.
The query parser also wraps a value in a list under every name a list field could
be read as (its validation alias, alias and Python name), so a list field whose
inactive alias or Python name equals the inbound name of a parameter that is not a
list raises `ValueError` too; two list fields may share such a name.

Nonempty declarations cannot accompany `query=Model` (`ValueError`). Omit
`adapter` or pass an exact `PydanticAdapter` instance; other adapters, including
subclasses, raise `TypeError`. `None` and empty mappings preserve existing
behavior. Objects/maps/nested models, unresolved references, absent or
non-keyword-only arguments, and Azure SDK-typed parameters raise `ValueError`.
References resolve against handler globals, so the handler must be a Python function,
a bound method or a `functools.partial` of one; a callable object raises `ValueError`.
Leading-underscore names and `BaseModel` attribute names are unsupported. Reserved
names are the request parameter, `context`, `http_request`, `body`, `query`, `path`,
`headers`, and `req_model`. A validated request value wins over an invocation keyword
argument.

Only declared names are hidden from the worker; real bindings remain visible.
Supported ordering is SDK binding decorators, outer logging, validation, then
application/DB injection using the inner wrapper's published signature. Foreign
metadata namespaces are preserved. Validation cannot see a future outer binding
named like an ordinary scalar: such a collision must fail worker indexing, and
is not universally detectable at decoration time. Use `query=Model` for custom
model policies or richer query structures.

### `path`

Use `path=PathModel` for route variables from `@app.route(route="...")`.

```python
class PathModel(BaseModel):
    item_id: int = Field(ge=1)


@validate_http(path=PathModel)
def get_item(req: func.HttpRequest, path: PathModel) -> dict[str, int]:
    return {"item_id": path.item_id}
```

### `headers`

Use `headers=HeadersModel` to validate inbound request headers.

```python
class HeadersModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    x_request_id: str = Field(alias="x-request-id")


@validate_http(headers=HeadersModel)
def inspect(req: func.HttpRequest, headers: HeadersModel) -> dict[str, str]:
    return {"request_id": headers.x_request_id}
```

Header names are matched case-insensitively against field names and aliases, so
`X-Request-ID`, `x-request-id`, and `X-REQUEST-ID` all populate the same field.

### `request_model` (deprecated)

!!! warning "Deprecated — use `body`"
    `request_model` is a deprecated alias for `body` and emits a
    `DeprecationWarning`. Prefer `body=` (which injects a parameter named
    `body`). `request_model` will be removed in a future release.

`request_model` is shorthand for body validation and injects a parameter named
`req_model`.

```python
class RequestModel(BaseModel):
    text: str


# Deprecated form (emits DeprecationWarning):
@validate_http(request_model=RequestModel)
def post(req: func.HttpRequest, req_model: RequestModel) -> dict[str, str]:
    return {"text": req_model.text}


# Preferred form:
@validate_http(body=RequestModel)
def post_preferred(req: func.HttpRequest, body: RequestModel) -> dict[str, str]:
    return {"text": body.text}
```

!!! warning "Mutual exclusivity"
    Do not combine `request_model` with `body`, `query`, `path`, or `headers`.

### `response_model`

Use `response_model=ModelOrType` to validate your handler output.

```python
class ResultModel(BaseModel):
    status: str


@validate_http(response_model=ResultModel)
def health(req: func.HttpRequest) -> dict[str, str]:
    return {"status": "ok"}
```

Also supports generic type forms like `list[ResultModel]`.

Validated response serialization can be customized with:

- `response_by_alias=False` to emit Python field names instead of serialization aliases.
- `response_exclude_none=True` to omit fields whose value is `None`.
- `response_exclude_unset=True` to omit fields that were not explicitly set.

These options require `response_model`; setting a non-default value without one
raises `ValueError` when the decorator is created. They apply only after response
validation. Returning `func.HttpResponse` still bypasses validation and
serialization, so these options do not modify its body. `response_exclude_none`
and `response_exclude_unset` affect payload presence only and do not change the
declared response schema.

Nested Pydantic models inside dataclass return values are serialized too, so a
dataclass holding a `BaseModel` field renders as plain JSON rather than raising
a serialization error.

!!! warning "Returning `None` with a non-Optional `response_model`"
    If the handler returns `None` while `response_model` does not allow `None`,
    response validation fails and the caller gets a sanitized
    `500` whose body is the generic
    `{"detail": [{"loc": [], "msg": "Internal Server Error", "type": "server_error"}]}`.
    The real cause is logged server-side, never leaked to the caller. Declare the model as Optional
    (for example `response_model=ResultModel | None`) when `None` is a valid
    outcome; then returning `None` produces a `204 No Content` instead.

### `adapter`

`adapter` allows plugging a custom implementation of the internal
`ValidationAdapter` protocol.

Default behavior uses `PydanticAdapter()` when omitted.

```python
@validate_http(body=RequestModel)  # adapter defaults to PydanticAdapter()
def handler(req: func.HttpRequest, body: RequestModel) -> dict[str, str]:
    return {"text": body.text}
```

!!! note "Advanced extension point"
    Most projects should keep the default adapter.

The complete method, lifetime, serialization, and exception contract is in
[Writing a custom adapter](adapters.md), including the reusable public
conformance suite.

Custom adapters use an explicit exception contract for all four request parsing
methods (`parse_body`, `parse_query`, `parse_path`, and `parse_headers`):

- raise `MalformedRequestError` for syntactically malformed client input (`400`)
- raise `AdapterValidationError` for model validation failures (`422`)
- let every other exception propagate as an adapter fault (`500`, logged and sanitized)

Plain `ValueError` is in the last category. There is no compatibility shim for
the former `ValueError`-to-`400` behavior; custom adapters must migrate malformed
syntax failures to `MalformedRequestError`.

### `error_formatter`

`error_formatter` customizes error response payloads per handler.

```python
from typing import Any


def formatter(exc: Exception, status_code: int) -> dict[str, Any]:
    message = str(exc) if status_code < 500 else "Internal Server Error"
    return {
        "error": {
            "code": f"VALIDATION_{status_code}",
            "message": message,
        }
    }


@validate_http(body=RequestModel, error_formatter=formatter)
def handler_custom(req: func.HttpRequest, body: RequestModel) -> dict[str, str]:
    return {"text": body.text}
```

The formatter receives the original exception for 4xx responses. For 5xx
responses it receives a public `InternalServerError` containing only
`"Internal Server Error"`; the original is logged once with traceback.

### `validation_error_response`

Declare a fixed request-schema error contract with
`ValidationErrorResponse(status_code=400, media_type="application/problem+json", response_model=Problem)`.
The status must be an integer 400–499 (not a boolean). Media types are bare
`application/json` or `application/<subtype>+json` (the subtype may contain further
`+`, as in `application/vnd.acme+problem+json`), normalized to lowercase;
parameters and wildcards are rejected. Non-default media or an error model
requires `error_formatter`. A status-only declaration can reuse the default body.

The synchronous formatter still receives the original classified status `422`.
It may return a dictionary, or an `ErrorResponseSpec(content=..., status_code=...,
media_type=..., headers=...)` on request-schema failures only. Without a fixed
declaration, omitted rich fields inherit 422 and JSON. With one, omitted fields
inherit the declaration and explicit disagreement fails closed. The optional
Pydantic model is compiled once, validates content, and filters subclass-only
fields during serialization. Success-response serialization options do not apply.

Malformed JSON 400, 413, 415, request resolution, response failures and handler
`HttpError` are not eligible, even `HttpError(422)`. Dictionary formatters retain
their existing behavior there; rich results produce sanitized 500. Formatter
exceptions, invalid results, model mismatch, cycles and nonfinite rich JSON also
produce the built-in sanitized 500 without retrying the formatter or adapter.

Rich headers accept a mapping or ordered pairs, copied per invocation. Names
must be ASCII HTTP tokens; values must be Latin-1 strings without CR/LF, DEL or
C0 controls except HTAB. Case-insensitive duplicates are rejected except
individual `Set-Cookie` pairs (one valid cookie per entry, never comma-joined).
`Content-Length`, `Transfer-Encoding`, `Connection`, `Keep-Alive`,
`Proxy-Authenticate`, `Proxy-Authorization`, `TE`, `Trailer`, `Upgrade` and
`Host` are prohibited. Supplied `Content-Type` must match the authoritative media
type after stripping whitespace and comparing case-insensitively.

Fixed declarations opt that endpoint into metadata v2. A custom formatter
without one omits the unknown request-error response: document application-owned
variants explicitly. Older v1-only consumers warn/degrade for v2; no consumer
runtime dependency is introduced. See [the metadata convention](METADATA_SPEC.md)
and [Problem Details example](examples/custom_error_handler.md).

### `expose_internal_errors` (unsafe opt-in)

`expose_internal_errors` defaults to `False`. Setting it to `True` passes the
original 5xx exception to `error_formatter`, restoring the old behavior. This
is unsafe because a formatter can expose internal details to clients.

### `status_code`

`status_code` sets the HTTP status code for successful responses (default
`200`). Use it for creation endpoints and similar cases.

```python
@validate_http(body=RequestModel, response_model=ResultModel, status_code=201)
def create_item(req: func.HttpRequest, body: RequestModel) -> ResultModel:
    return ResultModel(status="created")
```

### `legacy_loc`

`legacy_loc` (default `False`) restores pre-0.13 error locations: `loc` values
omit the leading input-source segment, so you get `["email"]` instead of
`["body", "email"]`. It is a one-cycle migration escape hatch and is ignored
when a custom `adapter` is supplied — configure that adapter directly instead.

```python
@validate_http(body=RequestModel, legacy_loc=True)
def legacy(req: func.HttpRequest, body: RequestModel) -> dict[str, str]:
    return {"text": body.text}
```

## Configuration patterns

### Pattern 1: simple body API

```python
@validate_http(body=RequestModel, response_model=ResultModel)
def create(req: func.HttpRequest, body: RequestModel) -> ResultModel:
    return ResultModel(status="created")
```

### Pattern 2: route-driven read API

```python
@validate_http(path=PathModel, query=QueryModel, response_model=ResultModel)
def get(req: func.HttpRequest, path: PathModel, query: QueryModel) -> ResultModel:
    return ResultModel(status=f"item={path.item_id},page={query.page}")
```

### Pattern 3: custom error contract

```python
@validate_http(body=RequestModel, response_model=ResultModel, error_formatter=formatter)
def create_custom(req: func.HttpRequest, body: RequestModel) -> ResultModel:
    return ResultModel(status="created")
```

## Defaults and operational behavior

- `adapter` defaults to `PydanticAdapter()`.
- No `response_model` means output is serialized without response schema validation.
- Returning `func.HttpResponse` bypasses response serialization/validation,
  including all `response_*` serialization options.
- 500-level internal pipeline errors are sanitized by default when no formatter is set.

!!! tip "Choose explicit response models"
    `response_model` catches accidental contract drift and is strongly recommended
    for public APIs.

## Related references

- [Strict API boundary models](strict-models.md)
- [API Reference](api.md)
- [Usage](usage.md)
- [Troubleshooting](troubleshooting.md)
- [FAQ](faq.md)
