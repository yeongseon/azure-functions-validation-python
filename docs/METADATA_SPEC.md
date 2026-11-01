# `endpoint` metadata convention — `azure-functions-validation` conformance

Status: **v1 default, v2 opt-in** · Owner namespace: `endpoint`

> **Scope of this document:** This document describes `azure-functions-validation`'s
> local conformance to the toolkit `endpoint` metadata **v1** convention. The
> convention is exchanged as plain JSON-compatible metadata. No package or
> repository is the canonical runtime owner — this is a **convention**, not a
> centralized binding spec. What follows describes how `azure-functions-validation`
> emits and canonicalizes its payload, plus its own internal (non-published)
> conformance artifacts.

> **Localization:** This document is an English-only technical document
> (the JSON Schema it links to is an internal conformance artifact of this
> package, not a source of truth other packages bind to).
> It is intentionally **not** part of the translated README set
> (`README.ko.md`, `README.ja.md`, `README.zh-CN.md`) and requires no translation
> updates when it changes.

## Purpose

> **Relationship to the worker contract:** This document is the *cross-package* contract (how sibling packages exchange `endpoint` metadata). The platform's *worker contract* — how the Azure Functions worker binds handler parameters by name — is explained separately in [How the worker binds handlers](https://yeongseon.dev/azure-functions-python/platform/how-the-worker-binds-handlers/). This page = cross-package convention; the worker-binding page = platform runtime contract.

The Azure Functions Python DX Toolkit lets sibling packages cooperate without
importing one another. Decorators attach a single dict to the wrapped handler
under the conventional attribute `_azure_functions_metadata`, keyed by a
package-owned **namespace** string. Consumers discover metadata by reading that
attribute — never by importing the producer.

The `endpoint` namespace is a **versioned, OpenAPI-ready metadata convention**.
Producer packages (`azure-functions-validation`, `azure-functions-langgraph`, …)
write it; the consumer (`azure-functions-openapi`) reads it and derives the
OpenAPI spec directly, instead of reconstructing OpenAPI shapes per producer.

The JSON Schema in
[`src/azure_functions_validation/schemas/endpoint.schema.json`](https://github.com/yeongseon/azure-functions-validation-python/blob/main/src/azure_functions_validation/schemas/endpoint.schema.json)
is an **internal conformance artifact of `azure-functions-validation`**: this
package validates its own emitted payload against it in tests. It is not
published, dereferenced, or shared as a runtime contract — each package owns
its own local conformance tests against the versioned dict convention.

## Distribution & sync

The versioned JSON-compatible namespace remains the integration boundary; no new
shared runtime distribution is warranted. The local schema is a producer-side
conformance artifact, not a second runtime dependency. The OpenAPI consumer reads
`endpoint` directly, validates its version, copies it and translates response
schemas to OpenAPI response content. It does not need Validation model classes.
`tests/test_openapi_consumer_contract.py` runs the real published OpenAPI bridge
against this producer in normal CI, detecting consumer/producer drift rather than
assuming matching schema file names imply compatibility. OpenAPI is a development
test dependency only; no sibling repository is modified or coordinated here.

For version 1, preserve existing field meanings and JSON-compatible values;
breaking field changes require a new namespace payload version and compatibility
tests. An unknown version must remain observable rather than silently treated as
the supported one. The `logging` namespace is independently owned by Logging;
Validation only detects its presence to warn about correlation-context decorator
order. It neither imports Logging nor consumes its private payload structure.

- The schema ships as package data inside
  `azure_functions_validation.schemas`, loaded via `importlib.resources`. No
  new runtime dependency is introduced; `jsonschema` is required only to
  *validate* payloads and is test-only.
- The schema is an **internal conformance artifact** of this package, not a
  shared/hosted contract. Other packages that emit the `endpoint` namespace
  own their own local conformance tests against the same versioned dict
  convention (same philosophy as the vendored `_metadata_helpers.py`).
- Local drift is caught mechanically: `endpoint.schema.sha256` pins the file
  digest and `make check-schema-hash` (wired into `make check-all`) fails on
  any change. When you intentionally change the schema, update the pin and
  bump the `version` field if the change is breaking.

## Payload shape (version 1)

```jsonc
{
  "version": 1,                     // const 1; consumers WARN (not fail) on unknown
  "request_body": { /* JSON Schema */ } | null,
  "request_body_required": true,    // true whenever a body model is configured (runtime rejects empty body)
  "parameters": [                   // OpenAPI parameter objects (query/path/header)
    { "name": "id", "in": "path", "required": true, "schema": { /* JSON Schema */ } }
  ],
  "responses": {                    // status-code (string) -> response object; or null
    "200": { "schema": { /* JSON Schema */ } },  // "description" optional; producer omits it in v1
    "422": { "schema": { /* validation-error envelope */ } } // added by this producer when request validation applies
  } | null,
  "summary": "…",                   // optional
  "description": "…",               // optional
  "tags": ["users"],                // optional
  "security": [ { /* requirement */ } ] // optional
}
```

### `path` and `method` are intentionally OMITTED

The Azure Functions route binding (`@app.route(route=…, methods=…)`) is the
single source of truth for path and HTTP methods. The consumer derives them at
scan time from the binding, so producers must not duplicate them here.

### `responses` is a non-exhaustive fallback description

`responses` is a **generic** part of the convention: a producer maps known HTTP
status codes to response objects carrying their JSON Schema, or emits `null`
when it has nothing to describe. What those responses
*are* is producer-specific. A non-Pydantic producer, or one that only emits
success responses, is under no obligation to document a `422` body — it simply
describes whatever its runtime actually returns.

This producer's default v1 emission describes the decorator's fallback path,
not every possible handler return. `ResponseSpec` status/header choices, direct
SDK returns and return annotations do not change emission or infer dynamic
statuses, Location or cookie schemas. There is no dynamic-response flag.
Application-authored documentation must declare additional outcomes. A future
declarative richer response contract, not the envelope itself, would justify
new metadata facts. Existing fixed error declarations still select v2.

## azure-functions-validation implementation

The rest of this document describes rules that are **specific to
`azure-functions-validation`** — how *this* producer generates its payload. They
are not obligations on the generic `endpoint` convention above; other producers
of the namespace implement their own equivalents.

### Parameter mapping and `required` rules (validation-specific)

`@validate_http` accepts three parameter models — `query=`, `path=`, and
`headers=` — and `build_endpoint_metadata` flattens each model's fields into
OpenAPI parameter objects. The model argument determines the `in` location:

| Decorator argument | Emitted `in` value |
| --- | --- |
| `query=Model` | `"query"` |
| `query_params={...}` (generated private model) | `"query"` |
| `path=Model` | `"path"` |
| `headers=Model` | `"header"` |

(Note the singular OpenAPI spelling `header`, not `headers`.) A body model
does **not** produce `parameters` entries — it is emitted as `request_body`.

Each field becomes one parameter object `{ "name", "in", "required", "schema" }`:

- **`name`** uses the field's inbound validation alias (`by_alias=True`), so it
  matches the wire contract rather than the Python attribute name. Configure
  aliases with Pydantic v2 `Field(alias=...)` / `alias_generator`.
- **`required`** rules:
  - `path` parameters are **always** `required: true` — a path segment cannot
    be absent from a matched route, regardless of the field's optionality.
  - `query` and `header` parameters are `required: true` only when the field
    appears in the model's JSON Schema `required` list (i.e. it has no default);
    otherwise `required: false`. This keys off the schema's `required` list, not
    the annotation — a field typed `Optional[...]` with no default is still
    required.
  - Body-required behaviour is separate: `request_body_required` is `true`
    whenever a body model is configured — see issue
    [#347](https://github.com/yeongseon/azure-functions-validation-python/issues/347).
- **`schema`** is the field's Pydantic-generated JSON Schema. If the field
  references a nested model via `$ref`, the parameter's `schema` carries a
  top-level `$defs` so the consumer can hoist it (the `$defs`-if-`$ref`
  invariant).

Scalar shorthand uses the same validation-mode parameter builder and endpoint
v1 shape, including defaults, constraints, nullability, arrays and the `422`
response. Default factories are not called for metadata. No internal model is
exported: legacy `validation["query"]` remains exactly the user's `query=`
argument, therefore `None` for shorthand. `endpoint` is the authoritative
documentation payload.

#### Repeated / array query parameters

There is no special "explode" flag in the payload. A repeated query parameter
is modelled as an ordinary field whose schema is an array — e.g. a
`list[str]` field emits `"schema": { "type": "array", "items": {…} }`. The
consumer derives OpenAPI array/`explode` semantics from that array schema; the
producer does not encode collection-style hints separately. Runtime parsing of
repeated `req.params` into a list is the adapter's responsibility and is out of
scope for this metadata contract.

### The `422` validation-error response (validation-specific)

`@validate_http` returns a `422` on request-validation failure, so when the
operation performs request validation — i.e. any of `body`, `query`, `path`, or
`headers` is a Pydantic model — **this producer** adds a `"422"` entry to
`responses` describing the standardized validation-error body the runtime
returns on invalid input:

```jsonc
{
  "type": "object",
  "required": ["detail"],
  "properties": {
    "detail": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["loc", "msg", "type"],
        "properties": {
          "loc": { "type": "array", "items": { "type": ["string", "integer"] } },
          "msg": { "type": "string" },
          "type": { "type": "string" }
        }
      }
    }
  }
}
```

The `422` schema is **self-contained** (no `$ref`, no `$defs`). It is emitted
independently of `response_model`: an operation with a request model but no
`response_model` still carries a `responses` map of just `{"422": …}`. When
there is no request model, no `422` is emitted. This documents the default
`{"detail": [...]}` envelope only; a custom `ErrorFormatter` may change the
runtime body. With a custom formatter and no fixed declaration, this producer
omits the fabricated request-error entry and retains other known hints.
Applications must declare their dynamic error variants explicitly.

## Fixed error contracts (version 2)

An explicit `ValidationErrorResponse` opts that endpoint into v2 while
`ENDPOINT_METADATA_VERSION = 1` remains the default. Request and parameter
fields are unchanged. Every response detail has required `content`, mapping
media types to objects with a required schema dictionary; response-level
`schema` is forbidden. `content: {}` explicitly means no body.

```json
{
  "version": 2,
  "responses": {
    "200": {"content": {"application/json": {"schema": {"type": "object"}}}},
    "400": {"content": {
      "application/problem+json": {"schema": {"type": "object"}},
      "application/json": {"schema": {}}
    }},
    "204": {"content": {}}
  }
}
```

The fixed status/media and serialization-mode error model schema are emitted.
Without a model, default Pydantic formatting uses the standard envelope; a
custom formatter or unknown custom-adapter error shape uses `{}`. Body endpoints
with fixed status 400 also include malformed JSON's `application/json` variant.
Its schema is unknown with a custom formatter. Same-media variants combine with
`anyOf`, unless `{}` subsumes them. Other known success responses are converted
to content maps, including body-less 204 for nullable output.

Optional `headers` maps names to objects requiring a schema dictionary and
optional description. They describe header schemas, not literal wire values;
Content-Type belongs to the content map. Status keys are 200–599; body-forbidden
204, 205 and 304 require empty content. Older v1-only consumers warn/degrade on
v2, never interpret it as v1. Validation has no OpenAPI runtime dependency, and
v2 conformance is locally tested without requiring a consumer release.


## Canonicalization rules (validation-specific)

`azure-functions-validation` generates its embedded schemas from Pydantic models
with **exactly** these settings so output is stable and consumer-mergeable. This
is how *this* producer happens to canonicalize; the generic convention only
requires plain JSON Schema with `$defs` left unresolved:

| Rule | Value |
| --- | --- |
| Request/parameter alias handling | `by_alias=True` |
| Response alias handling | Matches `response_by_alias` (default `True`) |
| Request schema mode | `mode='validation'` |
| Response schema mode | `mode='serialization'` |
| Ref template | Pydantic default `#/$defs/{model}` |
| `$defs` | **left UNRESOLVED** — the consumer hoists them to `components/schemas` |
| Generator class | Pydantic default `GenerateJsonSchema` (pin explicitly if customized; Pydantic minor bumps can change output) |
| `request_body_required` | `True` whenever a body model is configured — the runtime unconditionally rejects an empty body with 422 regardless of field optionality (#347) |

The response-schema mode above applies to **Pydantic-derived response-model
schemas**. The `422` validation-error response schema is produced directly
(not from a Pydantic model) and is unaffected by these settings.
`response_exclude_none` and `response_exclude_unset` affect runtime payload
presence but do not change the response schema.

### Supported `body`/`response_model` annotations (validation-specific)

The runtime accepts any annotation `pydantic.TypeAdapter` can validate
(or serialize) for `body=` and `response_model=` — not only a direct
`BaseModel` subclass. `build_endpoint_metadata` mirrors that same contract, so
a working typed endpoint is never silently under-documented. Supported forms
include direct models, `list[Model]` and other generic collections,
`Optional[Model]` / `Model | None`, `Union[...]` of several models, and
`Annotated[Model, ...]`. Each is reduced to the same canonicalization rules
above (validation mode for `request_body`, serialization mode plus
`response_by_alias` for `responses`), with every referenced model's `$defs`
collected the same way.

A **nullable** `response_model` (e.g. `Model | None`) is additionally split in
`responses`: the success status carries only the non-null schema — this
producer never actually serializes a `null` body under that status — and a
separate `"204"` entry (with no `schema`) documents the real outcome when a
validated result is `None`, matching `_build_response`'s own behavior in
`pipeline.py`.

A `body`/`response_model` value this package cannot turn into a schema at
all — for example, a marker type meaningful only to a custom
`ValidationAdapter` passed via `adapter=` — is silently omitted from
`request_body`/`responses` exactly as if nothing were configured, rather than
raising. This preserves existing custom-backend usage unchanged.

### Structural rule: `$defs` if `$ref`

Any embedded schema that contains a `$ref` **anywhere** MUST carry a top-level
`$defs` mapping. This guards against a producer pre-resolving (or dropping)
definitions, which would break the consumer's hoisting and make it no longer
the sole `$ref`-collision authority. This rule is not expressible in JSON Schema
alone and is enforced by
`azure_functions_validation.schemas.assert_defs_present_if_ref_used`.

## Consumer discipline

- Consumers MUST read the payload via an explicit allowlist / typed reader —
  never `**payload`-splat into a call. New optional keys must be additively
  ignorable.
- Consumers MUST treat an unknown `version` as a warning and fall back to their
  prior discovery path, not raise.
- Consumers remain the sole authority for `$ref` collision resolution; embedded
  `$defs` are inputs, not final `components/schemas`.

## Versioning policy

- `version` starts at `1`. Bump only on a **breaking** payload change.
- Additive, optional fields do **not** bump the version.
- On a bump, update the schema, its SHA-256 pin, and this spec, and coordinate
  producer/consumer support as needed before shipping the breaking version.
  Packages release independently — there is no coordinated release train.

## Internal helpers (not a public API)

This package ships a few schema helpers that it uses **for its own conformance
tests only**. They are intentionally **not** a supported cross-package public
API: sibling producers/consumers of the `endpoint` namespace MUST NOT import
them, and they may change or move without a deprecation cycle. Other packages
should implement their own local conformance checks against the versioned dict
convention described above (the same philosophy as the vendored
`_metadata_helpers.py`).

For reference, the internal helpers this package uses in its own test suite are:

- `ENDPOINT_METADATA_VERSION` — the current namespace version (`1`).
- `load_endpoint_schema()` — returns a fresh copy of the shipped JSON Schema.
- `endpoint_schema_sha256()` — hex digest of the shipped schema bytes.
- `assert_defs_present_if_ref_used()` — structural guard used in tests.

> These names are documented here to explain how this package validates itself,
> not to encourage `from azure_functions_validation.schemas import ...` in other
> packages. Treat them as internal.
