# Hello Validation Example

Minimal Azure Functions example showing how `validate_http` could be used in a function app.

```python
import json

import azure.functions as func
from pydantic import BaseModel

from azure_functions_validation import validate_http


class HelloRequest(BaseModel):
    name: str


class HelloResponse(BaseModel):
    message: str


app = func.FunctionApp()


@app.function_name(name="hello_validation")
@app.route(route="hello_validation", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(body=HelloRequest, response_model=HelloResponse)
def main(body: HelloRequest) -> HelloResponse:
    return HelloResponse(message=f"Hello {body.name}")


@app.function_name(name="raw_http_response")
@app.route(route="raw_http_response", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def raw_http_response(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(json.dumps({"message": "ok"}), mimetype="application/json")
```
