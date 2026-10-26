# Adapter extension surface evaluation

Decision: **retain the complete public extension contract**. Pydantic is the only
shipped backend. Custom implementations in tests and the adapter guide demonstrate
the supported seam, not a second shipped framework or verified production usage.
Lack of external usage evidence does not prove that a public API is unused.
No deprecation, deletion, plugin registry or new configuration option is justified.

## Surface inventory

| Contract | Default path | Advanced path and repository evidence |
| --- | --- | --- |
| `parse_body(req, model)` | Bounded UTF-8/JSON parsing and model validation | Custom parsing; `test_body_adapter_cache.py` preserves the existing custom signature |
| `parse_query`, `parse_path`, `parse_headers` | Aliases, string normalization, source-prefixed errors | Faulting/malformed adapters in pipeline and aggregation tests preserve error classification and order |
| `validate_response(obj, model, type_adapter=...)` | Declared-model validation with optional prepared hint | `_NativeAdapter` in `test_custom_response_backend.py` supports an ordinary schema-less class |
| `serialize(obj)` | Model-free JSON-compatible output | Custom content/content type; unexpected backend faults become controlled 500s |
| `serialize_response(obj, model, ...)` | Declared-model-only output, aliases and exclusion flags | Native backend sync/async tests prove the configured serializer is called |
| `format_error(exc)` | Default request-error envelope | Handler formatter precedence and upstream 5xx sanitization |
| `AdapterConformanceTests` | Pydantic conformance suite | BrokenJsonAdapter proves incorrect malformed-input classification is detected |

The public protocol lives in `adapter.py`, the public mixin in `conformance.py`,
and extension guidance in `docs/adapters.md`. `_NativeAdapter` and deliberately
broken/faulting adapters are test fixtures, not additional supported distributions.
This inventory makes no claim about usage outside this repository.

## Internal branches and consolidation decision

The pipeline selects configured request sources, calls parsing methods once and
injects by name. Aggregation preserves ordered error collection; it is not a second
backend implementation. WorkerCompat hides validation-injected parameters while
preserving actual trigger names and independent bindings. These host contracts
cannot be removed merely because a default Pydantic path looks simpler.

Response validation and model-aware serialization are intentionally separate.
Validation can return a subclass instance with private fields; replacing declared
model serialization with runtime-type serialization leaks those fields. Optional
Pydantic TypeAdapter construction must also remain non-fatal for a native model
owned by a custom backend. The hint is optional, not a required backend capability.

Two focused reductions are already backed by evidence:

- #598 removed redundant adjacent response exception branches after status,
  formatter disclosure and original-exception logging characterization passed.
- #595 reuses static body adapters only for the default decorator-owned backend.
  It adds no custom-adapter kwargs and no shared mutable request cache. See
  [measurements and limits](../body-adapter-performance.md).

No further hook deletion or argument transformation is proposed. A future internal
extraction needs a concrete duplicated behavior and contract tests first, not an
assumption of no users or a code-length target. Public API removal would require
separately staged compatibility review and migration; neither occurs here.

## Preservation evidence

Normal `@validate_http(body=..., response_model=...)` remains configuration-free
beyond its models. The unchanged conformance, SDK worker binding, native response,
subclass filtering, sanitized error, formatter precedence and async tests preserve
the extension contract. Adapter instances are reused concurrently: implementations
must be stateless or thread-safe. Cache schema machinery only, never request values
or mutable error details. The default prepared cache obeys that boundary.

This repository-local decision is not certification of arbitrary external
frameworks. A new backend needs its own evidence and scope, not a new plugin system.
