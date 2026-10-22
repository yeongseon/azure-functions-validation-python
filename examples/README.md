# Examples

These are local-only demonstrations, not production security templates. Anonymous
routes, in-memory stores and custom formatter output need explicit production
authentication, limits and redaction. The E2E app is ephemeral public certification
infrastructure using synthetic data only. See [SECURITY.md](../SECURITY.md).

`azure-functions-validation` keeps a growing set of smoke-tested examples:

| Role | Path | Description |
| --- | --- | --- |
| Representative | `examples/hello_validation` | Minimal body validation and typed response flow. |
| Complex | `examples/profile_validation` | Combined query, path, and header validation with a typed response model. |
| Focused | `examples/async_validation` | Async handler validation with typed request and response models. |
| Focused | `examples/custom_error_handler` | Custom validation error formatting for HTTP handlers. |
| Comprehensive | `examples/crud_api` | Task management CRUD API covering body, query, path, list response, request_model shorthand, and HttpResponse bypass. |
| E2E | `examples/e2e_app` | End-to-end test app with health check and validated item creation. |

Focused examples are intentionally smaller than the representative and complex examples.
They exist to keep one advanced pattern easy to inspect and easy to smoke-test.
