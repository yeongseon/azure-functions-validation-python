"""
Hello Validation Example - Azure Functions with validation.

This example demonstrates how to use azure-functions-validation
in a Python Azure Functions app.
"""

import azure.functions as func
from pydantic import BaseModel, Field

from azure_functions_validation import validate_http


class HelloRequest(BaseModel):
    """Request model for hello endpoint."""

    name: str = Field(..., min_length=1, max_length=50, description="User's name")
    count: int = Field(1, ge=1, le=10, description="Number of times to greet")


class HelloResponse(BaseModel):
    """Response model for hello endpoint."""

    message: str
    count: int


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str
    details: str | None = None


# Create the function app
app = func.FunctionApp()


@app.function_name(name="hello_validation")
@app.route(route="hello", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(body=HelloRequest, response_model=HelloResponse)
def hello_validation(body: HelloRequest) -> HelloResponse:
    """
    Greet a user with validation.

    This endpoint demonstrates:
    - Request body validation (name and count fields)
    - Response model validation and serialization
    - Automatic error handling (422 for validation errors)
    """
    greeting = " ".join([f"Hello {body.name}!"] * body.count)
    return HelloResponse(message=greeting, count=body.count)


@app.function_name(name="hello_dict")
@app.route(route="hello_dict", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(body=HelloRequest, response_model=HelloResponse)
def hello_dict(body: HelloRequest) -> dict:
    """
    Return dict that gets validated against HelloResponse.

    Demonstrates response validation - dict must match HelloResponse schema.
    """
    return {"message": f"Hello {body.name}!", "count": body.count}


@app.function_name(name="hello_custom_response")
@app.route(route="hello_custom", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(body=HelloRequest)
def hello_custom_response(body: HelloRequest) -> func.HttpResponse:
    """
    Return custom HttpResponse (bypasses validation).

    Demonstrates HttpResponse bypass - decorator doesn't validate or serialize.
    """
    import json

    return func.HttpResponse(
        body=json.dumps({"custom": f"Hello {body.name}!", "count": body.count}),
        mimetype="application/json",
        status_code=200,
    )


@app.function_name(name="echo_async")
@app.route(route="echo", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(body=HelloRequest, response_model=HelloResponse)
async def echo_async(body: HelloRequest) -> HelloResponse:
    """
    Async handler example.

    Demonstrates async handler support.
    """
    return HelloResponse(message=f"Echo: {body.name}", count=body.count)


@app.function_name(name="health")
@app.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def health(req: func.HttpRequest) -> func.HttpResponse:
    """
    Health check endpoint (no validation).

    Simple endpoint without validation to verify the app is running.
    """
    import json

    return func.HttpResponse(
        body=json.dumps({"status": "healthy"}),
        mimetype="application/json",
        status_code=200,
    )
