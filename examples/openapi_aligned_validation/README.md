# OpenAPI-Aligned Validation Example

This example shows how to keep validation behavior and OpenAPI-oriented error metadata aligned.

It does not require `azure-functions-openapi` directly. Instead, it uses the OpenAPI helper utilities
from `azure-functions-validation` to prepare reusable response metadata.

## Bridge helper

The `get_openapi_response_metadata()` function generates a complete `@openapi(response=...)`-compatible
dict from your validation models in a single call:

```python
from azure_functions_validation.openapi import get_openapi_response_metadata

OPENAPI_RESPONSES = get_openapi_response_metadata(
    body=WidgetRequest,
    response_model=WidgetResponse,
)
# Returns {"200": {...}, "422": {...}} ready for @openapi(response=...)
```

## Expected outcomes

- valid request body -> typed `WidgetResponse`
- invalid request body -> structured `422` validation error
- reusable `OPENAPI_RESPONSES` dict for `@openapi(response=...)` in `azure-functions-openapi`
- legacy `OPENAPI_422_SCHEMA` and `OPENAPI_422_EXAMPLES` still available for fine-grained control
