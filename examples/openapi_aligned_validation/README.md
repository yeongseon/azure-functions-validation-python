# OpenAPI-Aligned Validation Example

This example shows how to keep validation behavior and OpenAPI-oriented error metadata aligned.

It does not require `azure-functions-openapi` directly. Instead, it uses the OpenAPI helper utilities
from `azure-functions-validation` to prepare reusable `422` schema and example payload data.

Expected outcomes:

- valid request body -> typed `WidgetResponse`
- invalid request body -> structured `422` validation error
- reusable `OPENAPI_422_SCHEMA` and `OPENAPI_422_EXAMPLES` for downstream documentation tooling
