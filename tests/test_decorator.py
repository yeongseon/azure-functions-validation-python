"""Tests for the validate_http decorator."""

import json
from typing import Any

from azure.functions import HttpRequest, HttpResponse
from pydantic import BaseModel, Field
import pytest

from azure_functions_validation import validate_http


class RequestModel(BaseModel):
    name: str
    count: int = Field(ge=1, le=100)


class ResponseModel(BaseModel):
    message: str
    status: str = "success"


class TestValidateHttpDecorator:
    """Test validate_http decorator functionality."""

    def test_basic_body_validation_success(self) -> None:
        """Test basic body validation with valid request."""

        @validate_http(body=RequestModel, response_model=ResponseModel)
        def handler(body: RequestModel) -> ResponseModel:
            return ResponseModel(message=f"Hello {body.name}")

        req = HttpRequest(
            method="POST",
            url="http://localhost/test",
            body=json.dumps({"name": "Alice", "count": 5}).encode(),
        )

        response = handler(req)

        assert isinstance(response, HttpResponse)
        assert response.status_code == 200
        assert response.mimetype == "application/json"
        body = json.loads(response.get_body())
        assert body["message"] == "Hello Alice"
        assert body["status"] == "success"

    def test_request_model_shorthand(self) -> None:
        """Test using request_model as shorthand for body."""

        @validate_http(request_model=RequestModel, response_model=ResponseModel)
        def handler(req: RequestModel) -> ResponseModel:
            return ResponseModel(message=f"Hello {req.name}")

        req = HttpRequest(
            method="POST",
            url="http://localhost/test",
            body=json.dumps({"name": "Bob", "count": 10}).encode(),
        )

        response = handler(req)

        assert isinstance(response, HttpResponse)
        assert response.status_code == 200
        body = json.loads(response.get_body())
        assert body["message"] == "Hello Bob"

    def test_invalid_json_returns_400(self) -> None:
        """Test invalid JSON returns 400 Bad Request."""

        @validate_http(body=RequestModel, response_model=ResponseModel)
        def handler(body: RequestModel) -> ResponseModel:
            return ResponseModel(message="Should not reach here")

        req = HttpRequest(
            method="POST",
            url="http://localhost/test",
            body=b"{invalid json}",
        )

        response = handler(req)

        assert isinstance(response, HttpResponse)
        assert response.status_code == 400
        body = json.loads(response.get_body())
        assert "detail" in body
        assert body["detail"][0]["type"] == "json_invalid"
        assert body["detail"][0]["loc"] == ["body"]

    def test_missing_body_returns_422(self) -> None:
        """Test missing body returns 422 Unprocessable Entity."""

        @validate_http(body=RequestModel, response_model=ResponseModel)
        def handler(body: RequestModel) -> ResponseModel:
            return ResponseModel(message="Should not reach here")

        req = HttpRequest(
            method="POST",
            url="http://localhost/test",
            body=b"",
        )

        response = handler(req)

        assert isinstance(response, HttpResponse)
        assert response.status_code == 422
        body = json.loads(response.get_body())
        assert "detail" in body
        assert body["detail"][0]["type"] == "missing"
        assert body["detail"][0]["loc"] == ["body"]

    def test_validation_error_returns_422(self) -> None:
        """Test validation error returns 422 Unprocessable Entity."""

        @validate_http(body=RequestModel, response_model=ResponseModel)
        def handler(body: RequestModel) -> ResponseModel:
            return ResponseModel(message="Should not reach here")

        req = HttpRequest(
            method="POST",
            url="http://localhost/test",
            body=json.dumps({"name": "Charlie", "count": 200}).encode(),  # count > 100
        )

        response = handler(req)

        assert isinstance(response, HttpResponse)
        assert response.status_code == 422
        body = json.loads(response.get_body())
        assert "detail" in body
        assert len(body["detail"]) > 0
        # Should have count in the error location
        error = body["detail"][0]
        assert "count" in str(error["loc"])

    def test_response_dict_validation_success(self) -> None:
        """Test returning dict with response validation."""

        @validate_http(body=RequestModel, response_model=ResponseModel)
        def handler(body: RequestModel) -> dict[str, Any]:
            return {"message": f"Hello {body.name}", "status": "ok"}

        req = HttpRequest(
            method="POST",
            url="http://localhost/test",
            body=json.dumps({"name": "Diana", "count": 15}).encode(),
        )

        response = handler(req)

        assert isinstance(response, HttpResponse)
        assert response.status_code == 200
        body = json.loads(response.get_body())
        assert body["message"] == "Hello Diana"
        assert body["status"] == "ok"

    def test_response_validation_error_returns_500(self) -> None:
        """Test response validation error returns 500 Internal Server Error."""

        @validate_http(body=RequestModel, response_model=ResponseModel)
        def handler(body: RequestModel) -> dict[str, Any]:
            return {"invalid": "response"}  # Missing required 'message' field

        req = HttpRequest(
            method="POST",
            url="http://localhost/test",
            body=json.dumps({"name": "Eve", "count": 20}).encode(),
        )

        response = handler(req)

        assert isinstance(response, HttpResponse)
        assert response.status_code == 500
        body = json.loads(response.get_body())
        assert "detail" in body
        assert body["detail"][0]["type"] == "response_validation_error"
        assert body["detail"][0]["loc"] == ["response"]

    def test_http_response_bypass(self) -> None:
        """Test that returning HttpResponse bypasses validation."""

        @validate_http(body=RequestModel, response_model=ResponseModel)
        def handler(body: RequestModel) -> HttpResponse:
            return HttpResponse(
                body=json.dumps({"custom": "response"}),
                mimetype="application/json",
                status_code=201,
            )

        req = HttpRequest(
            method="POST",
            url="http://localhost/test",
            body=json.dumps({"name": "Frank", "count": 25}).encode(),
        )

        response = handler(req)

        assert isinstance(response, HttpResponse)
        assert response.status_code == 201
        body = json.loads(response.get_body())
        assert body["custom"] == "response"

    def test_no_response_model_serialization(self) -> None:
        """Test serialization without response_model."""

        @validate_http(body=RequestModel)
        def handler(body: RequestModel) -> dict[str, Any]:
            return {"message": f"Hello {body.name}"}

        req = HttpRequest(
            method="POST",
            url="http://localhost/test",
            body=json.dumps({"name": "Grace", "count": 30}).encode(),
        )

        response = handler(req)

        assert isinstance(response, HttpResponse)
        assert response.status_code == 200
        assert response.mimetype == "application/json"
        body = json.loads(response.get_body())
        assert body["message"] == "Hello Grace"

    def test_string_response_without_model(self) -> None:
        """Test returning string without response_model."""

        @validate_http(body=RequestModel)
        def handler(body: RequestModel) -> str:
            return f"Hello {body.name}"

        req = HttpRequest(
            method="POST",
            url="http://localhost/test",
            body=json.dumps({"name": "Henry", "count": 35}).encode(),
        )

        response = handler(req)

        assert isinstance(response, HttpResponse)
        assert response.status_code == 200
        assert response.mimetype == "text/plain; charset=utf-8"
        assert response.get_body().decode() == "Hello Henry"

    def test_bytes_response_without_model(self) -> None:
        """Test returning bytes without response_model."""

        @validate_http(body=RequestModel)
        def handler(body: RequestModel) -> bytes:
            return b"binary data"

        req = HttpRequest(
            method="POST",
            url="http://localhost/test",
            body=json.dumps({"name": "Iris", "count": 40}).encode(),
        )

        response = handler(req)

        assert isinstance(response, HttpResponse)
        assert response.status_code == 200
        assert response.mimetype == "application/octet-stream"
        assert response.get_body() == b"binary data"

    def test_async_handler_success(self) -> None:
        """Test async handler with validation."""

        @validate_http(body=RequestModel, response_model=ResponseModel)
        async def handler(body: RequestModel) -> ResponseModel:
            return ResponseModel(message=f"Hello {body.name}")

        req = HttpRequest(
            method="POST",
            url="http://localhost/test",
            body=json.dumps({"name": "Jack", "count": 45}).encode(),
        )

        # Run async handler
        import asyncio

        response = asyncio.run(handler(req))

        assert isinstance(response, HttpResponse)
        assert response.status_code == 200
        body = json.loads(response.get_body())
        assert body["message"] == "Hello Jack"

    def test_async_handler_validation_error(self) -> None:
        """Test async handler with validation error."""

        @validate_http(body=RequestModel, response_model=ResponseModel)
        async def handler(body: RequestModel) -> ResponseModel:
            return ResponseModel(message="Should not reach here")

        req = HttpRequest(
            method="POST",
            url="http://localhost/test",
            body=json.dumps({"name": "Kate", "count": 150}).encode(),  # count > 100
        )

        import asyncio

        response = asyncio.run(handler(req))

        assert isinstance(response, HttpResponse)
        assert response.status_code == 422

    def test_access_http_request_parameter(self) -> None:
        """Test accessing original HttpRequest via http_request parameter."""

        @validate_http(request_model=RequestModel, response_model=ResponseModel)
        def handler(req: RequestModel, http_request: HttpRequest) -> ResponseModel:
            user_agent = http_request.headers.get("User-Agent", "unknown")
            return ResponseModel(message=f"Hello {req.name} from {user_agent}")

        req = HttpRequest(
            method="POST",
            url="http://localhost/test",
            body=json.dumps({"name": "Laura", "count": 50}).encode(),
            headers={"User-Agent": "TestClient/1.0"},
        )

        response = handler(req)

        assert isinstance(response, HttpResponse)
        assert response.status_code == 200
        body = json.loads(response.get_body())
        assert "TestClient/1.0" in body["message"]

    def test_configuration_error_both_request_model_and_body(self) -> None:
        """Test that specifying both request_model and body raises error."""
        with pytest.raises(ValueError, match="Cannot specify both"):

            @validate_http(request_model=RequestModel, body=RequestModel)
            def handler(body: RequestModel) -> ResponseModel:
                return ResponseModel(message="test")

    def test_no_body_model_passes_request_through(self) -> None:
        """Test that no body model allows passing HttpRequest through."""

        @validate_http(response_model=ResponseModel)
        def handler(req: HttpRequest) -> ResponseModel:
            return ResponseModel(message="No body validation")

        req = HttpRequest(
            method="GET",
            url="http://localhost/test",
            body=b"",  # Empty body for GET request
        )

        response = handler(req)

        assert isinstance(response, HttpResponse)
        assert response.status_code == 200
        body = json.loads(response.get_body())
        assert body["message"] == "No body validation"
