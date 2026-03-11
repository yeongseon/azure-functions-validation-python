# Custom Error Handler

Use this example when you want to customize how `validate_http` formats validation errors in your response.

## What It Shows

- typed body validation with a custom error formatter
- custom error response structure instead of the default `{"detail": [...]}` envelope
- mapping validation errors to domain-specific error codes

## Example Path

- `examples/custom_error_handler`

## Key Pattern

```python
def custom_error_formatter(exc: Exception, status_code: int) -> dict[str, object]:
    return {
        "error": {
            "code": f"VALIDATION_{status_code}",
            "message": str(exc),
        }
    }


@validate_http(body=CommentRequest, error_formatter=custom_error_formatter)
def create_comment(req: func.HttpRequest, body: CommentRequest) -> dict[str, str]:
    return {"text": body.text, "status": "accepted"}
```

## Smoke Coverage

This example is smoke-tested for:

- a valid typed response
- a structured validation error with custom formatter applied
