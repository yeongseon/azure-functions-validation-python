# Changelog

All notable changes to this project will be documented in this file.

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
