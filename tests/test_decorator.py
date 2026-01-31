"""Tests for the @validate_http decorator."""

import json
from unittest.mock import Mock

import pytest
from azure.functions import HttpRequest, HttpResponse

from azure_functions_validation import validate_http
from azure_functions_validation.adapter import PydanticAdapter
from pydantic import BaseModel, Field
from pydantic import ValidationError as PydanticValidationError


# Test models
class UserModel(BaseModel):
    """Test model for user data."""

    name: str = Field(min_length=3, max_length=50)
    age: int = Field(ge=0, le=150)


class ResponseModel(BaseModel):
    """Test model for response data."""

    message: str
    status: str = "success"


class QueryModel(BaseModel):
    """Test model for query parameters."""

    limit: int = Field(ge=1, le=100, default=10)
    offset: int = Field(ge=0, default=0)


class PathModel(BaseModel):
    """Test model for path parameters."""

    user_id: int = Field(ge=1)


class HeaderModel(BaseModel):
    """Test model for headers."""

    authorization: str
    user_agent: str = Field(default="unknown")


# Fixtures
@pytest.fixture
def mock_request_factory():
    """Factory for creating mock HttpRequest objects."""

    def _create_request(
        body: bytes = b"",
        params: dict = None,
        route_params: dict = None,
        headers: dict = None,
    ):
        request = Mock(spec=HttpRequest)
        request.get_body.return_value = body
        request.params = params or {}
        request.route_params = route_params or {}
        request.headers = headers or {}
        return request

    return _create_request


@pytest.fixture
def adapter():
    """Create a PydanticAdapter instance."""
    return PydanticAdapter()


# Test successful validation
class TestSuccessfulValidation:
    """Tests for successful validation scenarios."""

    def test_body_validation_sync(self, mock_request_factory):
        """Test successful body validation with sync handler."""

        @validate_http(body=UserModel, response_model=ResponseModel)
        def sync_handler(req: HttpRequest, body: UserModel) -> ResponseModel:
            return ResponseModel(message=f"Hello {body.name}")

        request = mock_request_factory(body=b'{"name": "Alice", "age": 30}')
        response = sync_handler(request)

        assert isinstance(response, HttpResponse)
        assert response.status_code == 200
        assert "application/json" in response.headers.get("Content-Type", "")

        data = json.loads(response.get_body().decode())
        assert data["message"] == "Hello Alice"
        assert data["status"] == "success"

    def test_body_validation_async(self, mock_request_factory):
        """Test successful body validation with async handler."""
        import asyncio

        @validate_http(body=UserModel, response_model=ResponseModel)
        async def async_handler(req: HttpRequest, body: UserModel) -> ResponseModel:
            return ResponseModel(message=f"Hello {body.name}")

        request = mock_request_factory(body=b'{"name": "Bob", "age": 25}')
        response = async_handler(request)

        assert isinstance(response, HttpResponse)
        assert response.status_code == 200

        data = json.loads(response.get_body().decode())
        assert data["message"] == "Hello Bob"

    def test_query_validation(self, mock_request_factory):
        """Test successful query parameter validation."""

        @validate_http(query=QueryModel)
        def query_handler(req: HttpRequest, query: QueryModel) -> ResponseModel:
            return ResponseModel(message=f"Limit: {query.limit}, Offset: {query.offset}")

        request = mock_request_factory(params={"limit": "20", "offset": "5"})
        response = query_handler(request)

        assert response.status_code == 200

        data = json.loads(response.get_body().decode())
        assert "Limit: 20, Offset: 5" in data["message"]

    def test_path_validation(self, mock_request_factory):
        """Test successful path parameter validation."""

        @validate_http(path=PathModel)
        def path_handler(req: HttpRequest, path: PathModel) -> ResponseModel:
            return ResponseModel(message=f"User ID: {path.user_id}")

        request = mock_request_factory(route_params={"user_id": "123"})
        response = path_handler(request)

        assert response.status_code == 200

        data = json.loads(response.get_body().decode())
        assert data["message"] == "User ID: 123"

    def test_headers_validation(self, mock_request_factory):
        """Test successful header validation."""

        @validate_http(headers=HeaderModel)
        def headers_handler(req: HttpRequest, headers: HeaderModel) -> ResponseModel:
            return ResponseModel(message=f"Auth: {headers.authorization}")

        request = mock_request_factory(
            headers={"authorization": "Bearer token123", "user-agent": "test-agent"}
        )
        response = headers_handler(request)

        assert response.status_code == 200

        data = json.loads(response.get_body().decode())
        assert data["message"] == "Auth: Bearer token123"

    def test_multiple_input_sources(self, mock_request_factory):
        """Test validation with multiple input sources."""

        @validate_http(
            body=UserModel,
            query=QueryModel,
            path=PathModel,
            response_model=ResponseModel,
        )
        def multi_handler(
            req: HttpRequest,
            body: UserModel,
            query: QueryModel,
            path: PathModel,
        ) -> ResponseModel:
            return ResponseModel(
                message=f"User {body.name} (ID: {path.user_id}) with limit {query.limit}"
            )

        request = mock_request_factory(
            body=b'{"name": "Charlie", "age": 35}',
            params={"limit": "15"},
            route_params={"user_id": "456"},
        )
        response = multi_handler(request)

        assert response.status_code == 200

        data = json.loads(response.get_body().decode())
        assert "User Charlie" in data["message"]
        assert "ID: 456" in data["message"]
        assert "limit 15" in data["message"]

    def test_request_model_shorthand(self, mock_request_factory):
        """Test request_model shorthand (alias for body)."""

        @validate_http(request_model=UserModel, response_model=ResponseModel)
        def shorthand_handler(req: HttpRequest, req_model: UserModel) -> ResponseModel:
            return ResponseModel(message=f"Hello {req_model.name}")

        request = mock_request_factory(body=b'{"name": "Diana", "age": 28}')
        response = shorthand_handler(request)

        assert response.status_code == 200

        data = json.loads(response.get_body().decode())
        assert data["message"] == "Hello Diana"

    def test_http_request_parameter(self, mock_request_factory):
        """Test passing original HttpRequest to handler."""

        @validate_http(body=UserModel, response_model=ResponseModel)
        def httpreq_handler(
            req: HttpRequest, body: UserModel, http_request: HttpRequest
        ) -> ResponseModel:
            user_agent = http_request.headers.get("User-Agent", "unknown")
            return ResponseModel(message=f"Hello {body.name} from {user_agent}")

        request = mock_request_factory(
            body=b'{"name": "Eve", "age": 32}', headers={"User-Agent": "TestBrowser/1.0"}
        )
        response = httpreq_handler(request)

        assert response.status_code == 200

        data = json.loads(response.get_body().decode())
        assert "Hello Eve from TestBrowser/1.0" in data["message"]


# Test error handling
class TestErrorHandling:
    """Tests for error handling scenarios."""

    def test_invalid_json_body(self, mock_request_factory):
        """Test 400 error for invalid JSON."""

        @validate_http(body=UserModel, response_model=ResponseModel)
        def handler(req: HttpRequest, body: UserModel) -> ResponseModel:
            return ResponseModel(message="success")

        request = mock_request_factory(body=b"{invalid json")
        response = handler(request)

        assert response.status_code == 400
        assert "application/json" in response.headers.get("Content-Type", "")

        data = json.loads(response.get_body().decode())
        assert "detail" in data
        assert len(data["detail"]) > 0
        assert data["detail"][0]["type"] == "value_error"

    def test_missing_body(self, mock_request_factory):
        """Test 422 error for missing required body."""

        @validate_http(body=UserModel, response_model=ResponseModel)
        def handler(req: HttpRequest, body: UserModel) -> ResponseModel:
            return ResponseModel(message="success")

        request = mock_request_factory(body=b"")
        response = handler(request)

        assert response.status_code == 422

        data = json.loads(response.get_body().decode())
        assert "detail" in data
        assert len(data["detail"]) > 0
        assert data["detail"][0]["type"] == "missing"

    def test_invalid_body_fields(self, mock_request_factory):
        """Test 422 error for invalid field values."""

        @validate_http(body=UserModel, response_model=ResponseModel)
        def handler(req: HttpRequest, body: UserModel) -> ResponseModel:
            return ResponseModel(message="success")

        # Name too short
        request = mock_request_factory(body=b'{"name": "Al", "age": 30}')
        response = handler(request)

        assert response.status_code == 422

        data = json.loads(response.get_body().decode())
        assert "detail" in data
        assert any(error["type"] == "string_too_short" for error in data["detail"])

    def test_invalid_query_parameters(self, mock_request_factory):
        """Test 422 error for invalid query parameters."""

        @validate_http(query=QueryModel)
        def handler(req: HttpRequest, query: QueryModel) -> ResponseModel:
            return ResponseModel(message="success")

        request = mock_request_factory(params={"limit": "0"})  # Too small
        response = handler(request)

        assert response.status_code == 422

        data = json.loads(response.get_body().decode())
        assert "detail" in data
        assert any(
            error["type"] in ["number_too_small", "too_small", "number_too_large"]
            for error in data["detail"]
        )

    def test_response_validation_error(self, mock_request_factory):
        """Test 500 error for response validation failure."""

        @validate_http(body=UserModel, response_model=ResponseModel)
        def handler(req: HttpRequest, body: UserModel) -> ResponseModel:
            # Return invalid data that doesn't match response model
            return {"invalid": "data"}  # Missing required 'message' field

        request = mock_request_factory(body=b'{"name": "Frank", "age": 40}')
        response = handler(request)

        assert response.status_code == 500

        data = json.loads(response.get_body().decode())
        assert "detail" in data
        assert len(data["detail"]) == 1
        assert data["detail"][0]["type"] == "response_validation_error"
        assert data["detail"][0]["loc"] == ["response"]


# Test HttpResponse bypass
class TestHttpResponseBypass:
    """Tests for HttpResponse bypass logic."""

    def test_direct_httpresponse_return(self, mock_request_factory):
        """Test bypass when handler returns HttpResponse directly."""

        @validate_http(body=UserModel, response_model=ResponseModel)
        def handler(req: HttpRequest, body: UserModel) -> ResponseModel:
            return HttpResponse("Direct response", status_code=201, headers={"X-Custom": "test"})

        request = mock_request_factory(body=b'{"name": "Grace", "age": 29}')
        response = handler(request)

        assert response is not None  # Should return the same HttpResponse object
        assert response.status_code == 201
        assert response.headers.get("X-Custom") == "test"
        assert response.get_body().decode() == "Direct response"


# Test configuration errors
class TestConfigurationErrors:
    """Tests for decorator configuration errors."""

    def test_request_model_with_body_conflict(self):
        """Test ValueError when request_model and body are both provided."""
        with pytest.raises(ValueError) as exc_info:

            @validate_http(request_model=UserModel, body=UserModel, response_model=ResponseModel)
            def handler(req: HttpRequest, body: UserModel) -> ResponseModel:
                return ResponseModel(message="success")

        assert "Cannot use request_model together with body/query/path/headers" in str(
            exc_info.value
        )

    def test_missing_httprequest_argument(self):
        """Test ValueError when handler doesn't accept HttpRequest."""

        with pytest.raises(ValueError) as exc_info:

            @validate_http(body=UserModel, response_model=ResponseModel)
            def handler(body: UserModel) -> ResponseModel:  # Missing req parameter
                return ResponseModel(message="success")

        assert "must accept an HttpRequest parameter" in str(exc_info.value)


# Test serialization
class TestSerialization:
    """Tests for response serialization."""

    def test_basemodel_response(self, mock_request_factory):
        """Test serialization of BaseModel response."""

        @validate_http(body=UserModel, response_model=ResponseModel)
        def handler(req: HttpRequest, body: UserModel) -> ResponseModel:
            return ResponseModel(message="test message", status="custom")

        request = mock_request_factory(body=b'{"name": "Henry", "age": 33}')
        response = handler(request)

        assert response.status_code == 200
        assert "application/json" in response.headers.get("Content-Type", "")

        data = json.loads(response.get_body().decode())
        assert data["message"] == "test message"
        assert data["status"] == "custom"

    def test_dict_response(self, mock_request_factory):
        """Test serialization of dict response."""

        @validate_http(body=UserModel)
        def handler(req: HttpRequest, body: UserModel) -> dict:
            return {"message": f"Hello {body.name}", "data": [1, 2, 3]}

        request = mock_request_factory(body=b'{"name": "Ivy", "age": 27}')
        response = handler(request)

        assert response.status_code == 200
        assert "application/json" in response.headers.get("Content-Type", "")

        data = json.loads(response.get_body().decode())
        assert data["message"] == "Hello Ivy"
        assert data["data"] == [1, 2, 3]

    def test_string_response(self, mock_request_factory):
        """Test serialization of string response."""

        @validate_http(body=UserModel)
        def handler(req: HttpRequest, body: UserModel) -> str:
            return f"Hello, {body.name}!"

        request = mock_request_factory(body=b'{"name": "Jack", "age": 31}')
        response = handler(request)

        assert response.status_code == 200
        assert "text/plain" in response.headers.get("Content-Type", "")
        assert response.get_body().decode() == "Hello, Jack!"

    def test_bytes_response(self, mock_request_factory):
        """Test serialization of bytes response."""

        @validate_http(body=UserModel)
        def handler(req: HttpRequest, body: UserModel) -> bytes:
            return f"Data for {body.name}".encode()

        request = mock_request_factory(body=b'{"name": "Kate", "age": 26}')
        response = handler(request)

        assert response.status_code == 200
        assert "application/octet-stream" in response.headers.get("Content-Type", "")
        assert response.get_body() == b"Data for Kate"
