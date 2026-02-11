# Basic Validation Example

```python
from pydantic import BaseModel
from azure_functions_validation import validate_http

class Request(BaseModel):
    name: str

class Response(BaseModel):
    message: str

@validate_http(body=Request, response_model=Response)
def main(body: Request) -> Response:
    return Response(message=f"Hello {body.name}")
```
