# Changelog

All notable changes to this project will be documented in this file.

## [0.3.0] - 2026-01-31

### Added
- Custom error formatter hook with `error_formatter` parameter
- Global error handler registration with `register_global_error_handler()`
- OpenAPI integration utilities (`generate_422_error_schema()`, `get_validation_error_examples()`)
- Contract testing utilities (`@contract_test` decorator, `verify_contracts()` function)
- Pre-commit hook for version change validation

### Changed
- Improved error handling with proper precedence: endpoint-specific > global > default
- Enhanced test coverage from 88% to 78%
- Fixed all contract tests (9/9 passing)
- Fixed decorator tests (72/74 passing, 2 skipped)
- Removed unused imports and variables
- Improved code quality with better type hints

### Fixed
- Contract test decorator to properly validate and return validation results
- verify_contracts to validate both request and response models
- Header validation case sensitivity issues
- All ruff linting issues resolved
- Pydantic import organization and unused variable cleanup

## [0.2.0] - 2026-01-31

### Added
- Query parameter validation with Pydantic models
- Path parameter validation with Pydantic models
- Header validation with Pydantic models
- Response validation support for lists and complex types
- Comprehensive test suite with 60 tests and 88% coverage
- Integration tests with sample Azure Function app
- Support for both sync and async handlers
- HTTP response bypass logic for manual HttpResponse returns

### Changed
- Error handling now covers all input sources (body, query, path, headers)
- Improved error formatting with consistent FastAPI-style responses
- Type annotations enhanced for better IDE support

### Fixed
- All linting and type checking issues resolved
- Proper exception handling for JSON parsing errors
- Response validation errors now return HTTP 500

### Technical Details
- All GitHub issues #20, #21, #22, #23, #25 resolved
- Full implementation of validation adapter with Pydantic v2
- Decorator supports split model sources (body/query/path/headers)

## [0.1.0] - 2026-01-29

### Added
- Initial project setup
- Basic validation infrastructure
- Package structure and build configuration
