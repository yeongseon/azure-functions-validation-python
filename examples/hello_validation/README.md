# Hello Validation Example

This example demonstrates how to use `azure-functions-validation` in an Azure Functions Python app.

## Structure

- `function_app.py` - Main application with example endpoints
- `requirements.txt` - Dependencies
- `host.json` - Azure Functions configuration

## Features Demonstrated

1. **Request Body Validation** - Automatic validation of incoming JSON
2. **Response Model Validation** - Ensure responses match expected schema
3. **Async Handler Support** - Works with both sync and async functions
4. **Error Handling** - Standard 422 responses for validation errors
5. **HttpResponse Bypass** - Return custom responses when needed

## Running Locally

### Prerequisites

- Python 3.10+
- Azure Functions Core Tools v4

### Steps

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Start the function app:

```bash
func start
```

3. Test the endpoints:

**Valid request:**
```bash
curl -X POST http://localhost:7071/api/hello \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice", "count": 3}'
```

Response:
```json
{
  "message": "Hello Alice! Hello Alice! Hello Alice!",
  "count": 3
}
```

**Invalid request (validation error):**
```bash
curl -X POST http://localhost:7071/api/hello \
  -H "Content-Type: application/json" \
  -d '{"name": "Bob", "count": 20}'
```

Response (422):
```json
{
  "detail": [
    {
      "loc": ["body", "count"],
      "msg": "Input should be less than or equal to 10",
      "type": "number_too_large"
    }
  ]
}
```

**Missing field:**
```bash
curl -X POST http://localhost:7071/api/hello \
  -H "Content-Type: application/json" \
  -d '{"count": 2}'
```

Response (422):
```json
{
  "detail": [
    {
      "loc": ["body", "name"],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```

## Endpoints

- `POST /api/hello` - Basic validation example
- `POST /api/hello_dict` - Return dict with validation
- `POST /api/hello_custom` - Custom HttpResponse bypass
- `POST /api/echo` - Async handler example
- `GET /api/health` - Health check (no validation)

## Code Example

```python
from pydantic import BaseModel, Field
from azure_functions_validation import validate_http
import azure.functions as func


class HelloRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    count: int = Field(1, ge=1, le=10)


class HelloResponse(BaseModel):
    message: str
    count: int


app = func.FunctionApp()


@app.function_name(name="hello_validation")
@app.route(route="hello", methods=["POST"])
@validate_http(body=HelloRequest, response_model=HelloResponse)
def hello_validation(body: HelloRequest) -> HelloResponse:
    greeting = " ".join([f"Hello {body.name}!"] * body.count)
    return HelloResponse(message=greeting, count=body.count)
```
