# Troubleshooting

This guide addresses common issues encountered when using the azure-functions-validation library. It covers installation, request/response validation, decorator configuration, and development environment setup.

## Installation and Environment

### Python Version Requirements
**Problem**: The library fails to import or shows syntax errors.
**Cause**: This library requires Python 3.10 or higher to support modern type hinting and Pydantic v2 features.
**Solution**: Ensure your environment (local and Azure) is running Python 3.10+. Check your version with:
```bash
python --version
```

### Pydantic v2 Requirement
**Problem**: `ImportError` or `AttributeError` related to Pydantic models.
**Cause**: The library specifically requires Pydantic v2 (>= 2.0, < 3.0). It is not compatible with Pydantic v1.
**Solution**: Update Pydantic in your requirements.txt or pyproject.toml:
```text
pydantic>=2.0,<3.0
```

### Missing azure-functions Package
**Problem**: `ModuleNotFoundError: No module named 'azure.functions'`.
**Cause**: The core Azure Functions SDK is not installed in the current environment.
**Solution**: Install the required SDK:
```bash
pip install azure-functions
```

### Virtual Environment Issues
**Problem**: Installed packages are not recognized by the Azure Functions host.
**Cause**: The host might be using a different Python interpreter or the virtual environment is not activated.
**Solution**: Ensure you activate your virtual environment before running or deploying.
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows
```

## Request Validation Issues

### Empty Request Body (422 Unprocessable Entity)
**Problem**: API returns 422 for a request that should have a body.
**Cause**: When a `body` or `request_model` is defined but the request body is empty, the library raises a `PydanticValidationError` with `type="missing"`.
**Solution**: Ensure the client sends a non-empty JSON body. If the body is optional, use `Optional[MyModel] = None` in the decorator.
```python
@validate_http(body=Optional[MyModel])
def handler(req: func.HttpRequest, body: Optional[MyModel]):
    ...
```

### Malformed JSON (400 Bad Request)
**Problem**: API returns 400 with "Invalid JSON" message.
**Cause**: The request body is not valid JSON. `PydanticAdapter` raises `ValueError("Invalid JSON")`.
**Solution**: Validate the JSON payload sent by the client. Standard JSON requires double quotes for keys and strings.

### Query Parameters as Strings
**Problem**: Query parameter validation fails for non-string types.
**Cause**: Azure Functions provides query parameters as strings. Pydantic handles coercion, but complex custom types might fail if they cannot be initialized from a string.
**Solution**: Use Pydantic's built-in coercion or custom validators.
```python
class QueryModel(BaseModel):
    id: int  # Pydantic will coerce "123" to 123
```

### Path Parameters and Route Templates
**Problem**: Path parameters are missing or validation fails.
**Cause**: The route template in `@app.route` must match the field names in your path model.
**Solution**:
```python
@app.route(route="users/{user_id}")
@validate_http(path=PathModel)
def handler(req, path: PathModel):
    ...
# PathModel should have a field named 'user_id'
```

### Header Case Sensitivity
**Problem**: Header validation fails even when the header is present.
**Cause**: HTTP headers are case-insensitive, but Pydantic field names are case-sensitive by default.
**Solution**: Use Pydantic `AliasChoices` or `Field(alias=...)` to match header names.
```python
from pydantic import Field, AliasChoices

class HeaderModel(BaseModel):
    content_type: str = Field(validation_alias=AliasChoices("Content-Type", "content-type"))
```

### request_model vs body Parameter
**Problem**: `ValueError: Cannot use request_model together with body/query/path/headers`.
**Cause**: `request_model` is a shorthand alias specifically for the `body`. It cannot be used if any other validation source is explicitly defined.
**Solution**: Use `body` instead of `request_model` when you need to validate multiple sources.

## Response Validation Issues

### ResponseValidationError (500 Internal Server Error)
**Problem**: API returns 500 with `response_validation_error`.
**Cause**: The value returned by the handler does not match the `response_model` schema.
**Solution**: Verify the handler returns a dictionary or model instance that satisfies the `response_model` constraints.

### Bypassing Response Validation
**Problem**: Response validation is skipped.
**Cause**: Returning an `azure.functions.HttpResponse` directly bypasses the validation and serialization layer.
**Solution**: This is intentional. If you need validation, return a Pydantic model instance or a dictionary.

### List Response Validation
**Problem**: Validating a list of objects fails.
**Cause**: Incorrect usage of `response_model`.
**Solution**: Use the standard Python list type hinting for the `response_model`.
```python
@validate_http(response_model=list[ItemModel])
def get_items(req: func.HttpRequest) -> list[ItemModel]:
    return [ItemModel(id=1), ItemModel(id=2)]
```

## Decorator Configuration Errors

### First Argument Requirement
**Problem**: `ValueError: Function X must accept an HttpRequest parameter as its first positional argument`.
**Cause**: The handler function must take an `HttpRequest` (or similar) as its first argument.
**Solution**: Ensure the signature starts with the request object.
```python
@validate_http(body=MyModel)
def my_function(req: func.HttpRequest, body: MyModel):
    ...
```

### Parameter Name Conflicts
**Problem**: `ValueError: Function X: first positional parameter 'body' conflicts with a @validate_http injected parameter`.
**Cause**: If you name the first parameter `body` and also use `body=MyModel` in the decorator, the names collide.
**Solution**: Rename the first parameter to `req` or `http_request`.

### Decorator Order
**Problem**: Validation does not trigger or arguments are not injected.
**Cause**: The `@validate_http` decorator must be placed closest to the function definition, below Azure Functions decorators like `@app.route`.
**Solution**:
```python
@app.route(route="hello")
@validate_http(body=MyModel)  # Correct: Below @app.route
def handler(req, body):
    ...
```

## Async Handler Issues

### Async Support
**Problem**: Confusion about whether `async` handlers are supported.
**Cause**: The library automatically detects `async` functions using `inspect.iscoroutinefunction`.
**Solution**: No special configuration is needed. `@validate_http` works with both sync and async handlers.

### Testing Async Handlers
**Problem**: `RuntimeError: no running event loop` during tests.
**Cause**: Testing async handlers requires an async test runner.
**Solution**: Use `pytest-anyio` or `pytest-asyncio` for your test suite.
```python
@pytest.mark.anyio
async def test_handler():
    pass  # Test logic here
```

## Custom Error Formatter Issues

### Formatter Signature
**Problem**: `TypeError` when the error formatter is called.
**Cause**: The custom error formatter must accept exactly two arguments: the exception and the status code.
**Solution**: Define the formatter with the signature `(Exception, int) -> dict`.
```python
def my_formatter(exc: Exception, status: int) -> dict:
    return {"error": str(exc), "code": status}
```

### Global Application
**Problem**: Formatter does not catch specific errors.
**Cause**: The formatter is applied to ALL error types within the handler's pipeline, including validation errors, JSON parsing errors, and response validation errors.
**Solution**: Use `isinstance` checks within the formatter if you need specific logic for different error types.

## Development and Testing

### PYTHONPATH Configuration
**Problem**: Tests or examples cannot find the `azure_functions_validation` module.
**Cause**: The `src/` directory is not in the Python path.
**Solution**: Include `src/` in your `PYTHONPATH`. The provided Makefile handles this automatically for most commands.
```bash
export PYTHONPATH=$PYTHONPATH:$(pwd)/src
```

### Quality Checks
**Problem**: Commits rejected by CI.
**Cause**: Linting or type checking failures.
**Solution**: Run the comprehensive check suite locally before committing:
```bash
make check-all
```

### Coverage Reports
**Problem**: Cannot find test coverage details.
**Cause**: Coverage files are generated but not viewed.
**Solution**: After running tests, check the `htmlcov/` directory or the terminal output.
```bash
make test
# View coverage in terminal or open htmlcov/index.html
```
