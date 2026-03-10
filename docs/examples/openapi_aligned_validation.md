# OpenAPI-Aligned Validation

Use this example when you want runtime validation and reusable validation error metadata to stay aligned.

## What It Shows

- request validation with `validate_http`
- typed response validation
- reusable `422` schema and examples for documentation tooling

## Example Path

- `examples/openapi_aligned_validation`

## Key Pattern

```python
OPENAPI_422_SCHEMA = generate_422_error_schema(WidgetRequest)
OPENAPI_422_EXAMPLES = get_validation_error_examples(WidgetRequest)


@validate_http(body=WidgetRequest, response_model=WidgetResponse)
def create_widget(req: func.HttpRequest, body: WidgetRequest) -> WidgetResponse:
    return WidgetResponse(id=1, name=body.name)
```

## Smoke Coverage

This example is smoke-tested for:

- a valid typed response
- exported `422` schema metadata
- exported `422` example payloads

