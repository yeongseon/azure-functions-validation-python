# API Reference

## Decorator

- `@validate_http(request_model, response_model, ...)`

## Error Handling

- `ResponseValidationError`
- `ErrorFormatter`

## Global Error Handler

## Functions

- `register_global_error_handler(exception_type, handler)`
- `clear_global_error_handlers()`
- `get_contract_schema(contract_type)`
- `get_request_contract_metadata(...)`
- `get_response_contract_metadata(response_model)`
- `get_validation_error_contract(request_model)`
- `describe_validation_contract(...)`
- `generate_422_error_schema(model)`
- `get_validation_error_examples(model)`
- `contract_test()`
- `verify_contracts(function, test_data, ...)`

See README for detailed examples and error response formats.
