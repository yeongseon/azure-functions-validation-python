# Examples

`azure-functions-validation` keeps a growing set of smoke-tested examples:

| Role | Path | Description |
| --- | --- | --- |
| Representative | `examples/hello_validation` | Minimal body validation and typed response flow. |
| Complex | `examples/profile_validation` | Combined query, path, and header validation with a typed response model. |
| Focused | `examples/async_validation` | Async handler validation with typed request and response models. |
| Focused | `examples/custom_error_handler` | Custom validation error formatting for HTTP handlers. |

Focused examples are intentionally smaller than the representative and complex examples.
They exist to keep one advanced pattern easy to inspect and easy to smoke-test.
