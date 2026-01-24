"""Tests for the validate_http decorator."""

# mypy: disable-error-code="arg-type, call-arg, attr-defined"

import json
from typing import Any, Optional

from azure.functions import HttpRequest, HttpResponse
from pydantic import BaseModel, Field
import pytest

from azure_functions_validation import validate_http


# Test models
class UserRequest(BaseModel):
    """User request model."""

    name: str = Field(..., min_length=1)
    age: Optional[int] = Field(None, ge=0)


class UserResponse(BaseModel):
    """User response model."""

    message: str
    user_name: Optional[str] = None


class SimpleModel(BaseModel):
    """Simple model for testing."""

    value: str


# Test functions
def test_valid_request_with_body_validation() -> None:
    """Test valid request with body validation."""

    @validate_http(body=UserRequest, response_model=UserResponse)
    def handler(req: UserRequest) -> UserResponse:
        return UserResponse(message=f"Hello {req.name}", user_name=req.name)

    # Create test request
    request = HttpRequest(
        method="POST",
        url="/api/test",
        body=json.dumps({"name": "John", "age": 30}).encode(),
    )

    # Call handler
    response = handler(request)

    # Verify response
    assert isinstance(response, HttpResponse)
    assert response.status_code == 200
    body = json.loads(response.get_body())
    assert body["message"] == "Hello John"
    assert body["user_name"] == "John"


def test_valid_request_with_request_model_shorthand() -> None:
    """Test valid request with request_model shorthand."""

    @validate_http(request_model=UserRequest, response_model=UserResponse)
    def handler(req: UserRequest) -> UserResponse:
        return UserResponse(message=f"Hello {req.name}", user_name=req.name)

    # Create test request
    request = HttpRequest(
        method="POST",
        url="/api/test",
        body=json.dumps({"name": "Jane"}).encode(),
    )

    # Call handler
    response = handler(request)

    # Verify response
    assert isinstance(response, HttpResponse)
    assert response.status_code == 200
    body = json.loads(response.get_body())
    assert body["message"] == "Hello Jane"


def test_response_model_validation() -> None:
    """Test response model validation."""

    @validate_http(request_model=UserRequest, response_model=UserResponse)
    def handler(req: UserRequest) -> UserResponse:
        return UserResponse(message="Test")

    # Create test request
    request = HttpRequest(
        method="POST",
        url="/api/test",
        body=json.dumps({"name": "Test"}).encode(),
    )

    # Call handler
    response = handler(request)

    # Verify response
    assert isinstance(response, HttpResponse)
    assert response.status_code == 200
    body = json.loads(response.get_body())
    assert body["message"] == "Test"


def test_invalid_json_returns_400() -> None:
    """Test that invalid JSON returns 400."""

    @validate_http(body=UserRequest)
    def handler(req: UserRequest) -> dict[str, Any]:
        return {"message": "ok"}

    # Create test request with invalid JSON
    request = HttpRequest(
        method="POST",
        url="/api/test",
        body=b"not valid json",
    )

    # Call handler
    response = handler(request)

    # Verify response
    assert isinstance(response, HttpResponse)
    assert response.status_code == 400
    body = json.loads(response.get_body())
    assert "detail" in body
    assert len(body["detail"]) == 1
    assert body["detail"][0]["type"] == "json_invalid"
    assert body["detail"][0]["loc"] == ["body"]
    assert "Invalid JSON" in body["detail"][0]["msg"]


def test_missing_body_returns_422() -> None:
    """Test that missing body returns 422."""

    @validate_http(body=UserRequest)
    def handler(req: UserRequest) -> dict[str, Any]:
        return {"message": "ok"}

    # Create test request with empty body
    request = HttpRequest(
        method="POST",
        url="/api/test",
        body=b"",
    )

    # Call handler
    response = handler(request)

    # Verify response
    assert isinstance(response, HttpResponse)
    assert response.status_code == 422
    body = json.loads(response.get_body())
    assert "detail" in body
    assert len(body["detail"]) > 0
    # Should have at least one error about missing field
    assert any(error["type"] in ["missing", "value_error"] for error in body["detail"])


def test_validation_error_returns_422() -> None:
    """Test that validation errors return 422."""

    @validate_http(body=UserRequest)
    def handler(req: UserRequest) -> dict[str, Any]:
        return {"message": "ok"}

    # Create test request with invalid data (empty name)
    request = HttpRequest(
        method="POST",
        url="/api/test",
        body=json.dumps({"name": "", "age": 30}).encode(),
    )

    # Call handler
    response = handler(request)

    # Verify response
    assert isinstance(response, HttpResponse)
    assert response.status_code == 422
    body = json.loads(response.get_body())
    assert "detail" in body
    assert len(body["detail"]) > 0
    # Check error structure
    error = body["detail"][0]
    assert "loc" in error
    assert "msg" in error
    assert "type" in error


def test_response_validation_error_returns_500() -> None:
    """Test that response validation errors return 500."""

    @validate_http(request_model=SimpleModel, response_model=UserResponse)
    def handler(req: SimpleModel) -> dict[str, Any]:
        # Return invalid response (missing required field)
        return {}

    # Create test request
    request = HttpRequest(
        method="POST",
        url="/api/test",
        body=json.dumps({"value": "test"}).encode(),
    )

    # Call handler
    response = handler(request)

    # Verify response
    assert isinstance(response, HttpResponse)
    assert response.status_code == 500
    body = json.loads(response.get_body())
    assert "detail" in body
    assert len(body["detail"]) == 1
    assert body["detail"][0]["type"] == "response_validation_error"
    assert body["detail"][0]["loc"] == ["response"]


def test_return_basemodel_instance() -> None:
    """Test returning BaseModel instance."""

    @validate_http(request_model=UserRequest, response_model=UserResponse)
    def handler(req: UserRequest) -> UserResponse:
        return UserResponse(message="Success", user_name=req.name)

    # Create test request
    request = HttpRequest(
        method="POST",
        url="/api/test",
        body=json.dumps({"name": "Alice"}).encode(),
    )

    # Call handler
    response = handler(request)

    # Verify response
    assert isinstance(response, HttpResponse)
    assert response.status_code == 200
    assert response.mimetype == "application/json"
    body = json.loads(response.get_body())
    assert body["message"] == "Success"
    assert body["user_name"] == "Alice"


def test_return_dict_with_validation() -> None:
    """Test returning dict with validation."""

    @validate_http(request_model=UserRequest, response_model=UserResponse)
    def handler(req: UserRequest) -> dict[str, Any]:
        return {"message": "Success", "user_name": req.name}

    # Create test request
    request = HttpRequest(
        method="POST",
        url="/api/test",
        body=json.dumps({"name": "Bob"}).encode(),
    )

    # Call handler
    response = handler(request)

    # Verify response
    assert isinstance(response, HttpResponse)
    assert response.status_code == 200
    body = json.loads(response.get_body())
    assert body["message"] == "Success"


def test_return_string_without_validation() -> None:
    """Test returning string without validation."""

    @validate_http(request_model=UserRequest)
    def handler(req: UserRequest) -> str:
        return f"Hello {req.name}"

    # Create test request
    request = HttpRequest(
        method="POST",
        url="/api/test",
        body=json.dumps({"name": "Charlie"}).encode(),
    )

    # Call handler
    response = handler(request)

    # Verify response
    assert isinstance(response, HttpResponse)
    assert response.status_code == 200
    assert response.mimetype == "text/plain; charset=utf-8"
    assert response.get_body().decode() == "Hello Charlie"


def test_return_bytes_without_validation() -> None:
    """Test returning bytes without validation."""

    @validate_http(request_model=UserRequest)
    def handler(req: UserRequest) -> bytes:
        return b"binary data"

    # Create test request
    request = HttpRequest(
        method="POST",
        url="/api/test",
        body=json.dumps({"name": "Dave"}).encode(),
    )

    # Call handler
    response = handler(request)

    # Verify response
    assert isinstance(response, HttpResponse)
    assert response.status_code == 200
    assert response.mimetype == "application/octet-stream"


def test_return_http_response_bypass_validation() -> None:
    """Test that HttpResponse bypasses validation."""

    @validate_http(request_model=UserRequest, response_model=UserResponse)
    def handler(req: UserRequest) -> HttpResponse:
        # Return custom HttpResponse (bypasses validation)
        return HttpResponse(
            body="Custom response",
            status_code=201,
            mimetype="text/plain",
        )

    # Create test request
    request = HttpRequest(
        method="POST",
        url="/api/test",
        body=json.dumps({"name": "Eve"}).encode(),
    )

    # Call handler
    response = handler(request)

    # Verify response (should be unchanged)
    assert isinstance(response, HttpResponse)
    assert response.status_code == 201
    assert response.mimetype == "text/plain"
    assert response.get_body().decode() == "Custom response"


def test_async_handler_support() -> None:
    """Test async handler support."""
    import asyncio

    @validate_http(request_model=UserRequest, response_model=UserResponse)
    async def handler(req: UserRequest) -> UserResponse:
        return UserResponse(message=f"Async hello {req.name}")

    # Create test request
    request = HttpRequest(
        method="POST",
        url="/api/test",
        body=json.dumps({"name": "Frank"}).encode(),
    )

    # Call handler (async)
    response = asyncio.run(handler(request))

    # Verify response
    assert isinstance(response, HttpResponse)
    assert response.status_code == 200
    body = json.loads(response.get_body())
    assert body["message"] == "Async hello Frank"


def test_access_original_http_request() -> None:
    """Test accessing original HttpRequest via parameter."""

    @validate_http(request_model=UserRequest, response_model=UserResponse)
    def handler(req: UserRequest, http_request: HttpRequest) -> UserResponse:
        # Access original request
        method = http_request.method
        return UserResponse(message=f"{method}: {req.name}")

    # Create test request
    request = HttpRequest(
        method="POST",
        url="/api/test",
        body=json.dumps({"name": "Grace"}).encode(),
    )

    # Call handler with http_request parameter
    response = handler(request, http_request=request)

    # Verify response
    assert isinstance(response, HttpResponse)
    assert response.status_code == 200
    body = json.loads(response.get_body())
    assert body["message"] == "POST: Grace"


def test_no_body_model_pass_through() -> None:
    """Test that no body model passes through."""

    @validate_http(response_model=UserResponse)
    def handler(req: HttpRequest) -> UserResponse:
        return UserResponse(message="No validation")

    # Create test request
    request = HttpRequest(
        method="POST",
        url="/api/test",
        body=json.dumps({"anything": "goes"}).encode(),
    )

    # Call handler
    response = handler(request)

    # Verify response
    assert isinstance(response, HttpResponse)
    assert response.status_code == 200
    body = json.loads(response.get_body())
    assert body["message"] == "No validation"


def test_both_body_and_request_model_raises_error() -> None:
    """Test that specifying both body and request_model raises error."""

    with pytest.raises(ValueError, match="Cannot specify both"):

        @validate_http(body=UserRequest, request_model=UserRequest)
        def handler(req: UserRequest) -> dict[str, Any]:
            return {"message": "ok"}


def test_error_detail_format() -> None:
    """Test that error details match PRD format."""

    @validate_http(body=UserRequest)
    def handler(req: UserRequest) -> dict[str, Any]:
        return {"message": "ok"}

    # Create test request with validation error
    request = HttpRequest(
        method="POST",
        url="/api/test",
        body=json.dumps({"name": "ok", "age": -5}).encode(),  # negative age
    )

    # Call handler
    response = handler(request)

    # Verify error format
    assert response.status_code == 422
    body = json.loads(response.get_body())
    assert "detail" in body
    assert isinstance(body["detail"], list)

    # Each error should have loc, msg, and type
    for error in body["detail"]:
        assert "loc" in error
        assert "msg" in error
        assert "type" in error
        assert isinstance(error["loc"], list)
        assert isinstance(error["msg"], str)
        assert isinstance(error["type"], str)


def test_http_request_in_kwargs() -> None:
    """Test handling HttpRequest in kwargs."""

    @validate_http(body=UserRequest)
    def handler(req: UserRequest) -> dict[str, Any]:
        return {"message": f"Hello {req.name}"}

    # Create test request
    request = HttpRequest(
        method="POST",
        url="/api/test",
        body=json.dumps({"name": "Test"}).encode(),
    )

    # Call handler with request as positional arg (normal case)
    response = handler(request)

    # Verify response
    assert isinstance(response, HttpResponse)
    assert response.status_code == 200
    body = json.loads(response.get_body())
    assert body["message"] == "Hello Test"


def test_missing_http_request_raises_error() -> None:
    """Test that missing HttpRequest raises ValueError."""

    @validate_http(body=UserRequest)
    def handler(req: UserRequest) -> dict[str, Any]:
        return {"message": "ok"}

    # Call handler without HttpRequest
    with pytest.raises(ValueError, match="HttpRequest not found"):
        handler()


def test_handler_raises_exception() -> None:
    """Test that handler exceptions propagate."""

    @validate_http(request_model=UserRequest)
    def handler(req: UserRequest) -> dict[str, Any]:
        raise RuntimeError("Something went wrong")

    # Create test request
    request = HttpRequest(
        method="POST",
        url="/api/test",
        body=json.dumps({"name": "Test"}).encode(),
    )

    # Call handler - exception should propagate
    with pytest.raises(RuntimeError, match="Something went wrong"):
        handler(request)


def test_async_invalid_json() -> None:
    """Test async handler with invalid JSON."""
    import asyncio

    @validate_http(body=UserRequest)
    async def handler(req: UserRequest) -> dict[str, Any]:
        return {"message": "ok"}

    # Create test request with invalid JSON
    request = HttpRequest(
        method="POST",
        url="/api/test",
        body=b"not valid json",
    )

    # Call handler
    response = asyncio.run(handler(request))

    # Verify response
    assert isinstance(response, HttpResponse)
    assert response.status_code == 400


def test_async_validation_error() -> None:
    """Test async handler with validation error."""
    import asyncio

    @validate_http(body=UserRequest)
    async def handler(req: UserRequest) -> dict[str, Any]:
        return {"message": "ok"}

    # Create test request with validation error
    request = HttpRequest(
        method="POST",
        url="/api/test",
        body=json.dumps({"name": ""}).encode(),
    )

    # Call handler
    response = asyncio.run(handler(request))

    # Verify response
    assert isinstance(response, HttpResponse)
    assert response.status_code == 422


def test_async_response_validation_error() -> None:
    """Test async handler with response validation error."""
    import asyncio

    @validate_http(request_model=SimpleModel, response_model=UserResponse)
    async def handler(req: SimpleModel) -> dict[str, Any]:
        return {}  # Invalid response

    # Create test request
    request = HttpRequest(
        method="POST",
        url="/api/test",
        body=json.dumps({"value": "test"}).encode(),
    )

    # Call handler
    response = asyncio.run(handler(request))

    # Verify response
    assert isinstance(response, HttpResponse)
    assert response.status_code == 500


def test_async_handler_exception() -> None:
    """Test that async handler exceptions propagate."""
    import asyncio

    @validate_http(request_model=UserRequest)
    async def handler(req: UserRequest) -> dict[str, Any]:
        raise RuntimeError("Async error")

    # Create test request
    request = HttpRequest(
        method="POST",
        url="/api/test",
        body=json.dumps({"name": "Test"}).encode(),
    )

    # Call handler - exception should propagate
    with pytest.raises(RuntimeError, match="Async error"):
        asyncio.run(handler(request))


def test_async_missing_http_request() -> None:
    """Test async handler with missing HttpRequest."""
    import asyncio

    @validate_http(body=UserRequest)
    async def handler(req: UserRequest) -> dict[str, Any]:
        return {"message": "ok"}

    # Call handler without HttpRequest
    with pytest.raises(ValueError, match="HttpRequest not found"):
        asyncio.run(handler())
