# API Reference

## Decorator

### `validate_http(...)`

Main decorator for request/response validation.

**Parameters**
- `body`: Pydantic model class for request body validation
- `query`: Pydantic model class for query parameter validation
- `path`: Pydantic model class for path parameter validation
- `headers`: Pydantic model class for header validation
- `request_model`: Shorthand for body model (alias for `body`)
- `response_model`: Pydantic model class for response validation
- `error_formatter`: Custom error formatter function
- `adapter`: Custom validation adapter instance

## Functions

- `register_global_error_handler(exception_type, handler)`
- `clear_global_error_handlers()`
- `generate_422_error_schema(model)`
- `get_validation_error_examples(model)`
- `contract_test()`
- `verify_contracts(function, test_data, ...)`

See README for detailed examples and error response formats.
