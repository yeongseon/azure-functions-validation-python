# Custom Error Handler Example

This example shows how to override the default validation error payload with a custom formatter.

It is useful when you need:

- a stable internal error code
- a custom error response envelope
- validation behavior that still relies on `validate_http`
