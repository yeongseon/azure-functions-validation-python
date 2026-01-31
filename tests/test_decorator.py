"""Tests for the @validate_http decorator."""

import json
from unittest.mock import Mock

from azure.functions import HttpRequest, HttpResponse
from pydantic import BaseModel, Field
import pytest

from azure_functions_validation import validate_http


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
    """Create a mock HttpRequest factory."""

    def _create_request(
        method="GET", url="http://example.com", body=b"", params=None, route_params=None
    ):
        """Create mock HttpRequest."""
        mock_req = Mock(spec=HttpRequest)
        mock_req.method = method
        mock_req.url = url
        mock_req.get_body.return_value = body
        mock_req.params = params or {}
        mock_req.route_params = route_params or {}
        mock_req.headers = {}

        return mock_req

    return _create_request


# Test successful validation
class TestSuccessfulValidation:
    """Tests for successful request/response validation."""

    def test_basic_body_validation(self, mock_request_factory):
        """Test basic body validation."""

        @validate_http(body=UserModel)
        def handler(req: HttpRequest, body: UserModel) -> ResponseModel:
            return ResponseModel(message=f"Hello, {body.name}")

        request = mock_request_factory(body=b'{"name": "Alice", "age": 30}')
        response = handler(request)

        assert response.status_code == 200
        data = json.loads(response.get_body().decode())
        assert data["message"] == "Hello, Alice"

    def test_query_validation(self, mock_request_factory):
        """Test query parameter validation."""

        @validate_http(body=UserModel, query=QueryModel)
        def handler(req: HttpRequest, body: UserModel, query: QueryModel) -> ResponseModel:
            return ResponseModel(message=f"Hello, {body.name}")

        request = mock_request_factory(
            body=b'{"name": "Bob", "age": 25}',
            params={"limit": "10", "offset": "0"},
        )
        response = handler(request)

        assert response.status_code == 200

    def test_path_validation(self, mock_request_factory):
        """Test path parameter validation."""

        @validate_http(body=UserModel, path=PathModel)
        def handler(req: HttpRequest, body: UserModel, path: PathModel) -> ResponseModel:
            return ResponseModel(message=f"Hello, {body.name}")

        request = mock_request_factory(
            body=b'{"name": "Charlie", "age": 35}', route_params={"user_id": "42"}
        )
        response = handler(request)

        assert response.status_code == 200

    def test_headers_validation(self, mock_request_factory):
        """Test headers validation."""

        @validate_http(body=UserModel, headers=HeaderModel)
        def handler(req: HttpRequest, body: UserModel, headers: HeaderModel) -> ResponseModel:
            return ResponseModel(message=f"Hello, {body.name}")

        request = mock_request_factory(body=b'{"name": "David", "age": 28}')
        request.headers = {"authorization": "Bearer token123", "user_agent": "Mozilla"}
        response = handler(request)

        assert response.status_code == 200


# Test validation errors
class TestValidationErrors:
    """Tests for validation error responses."""

    def test_body_validation_error(self, mock_request_factory):
        """Test 422 error for invalid body."""

        @validate_http(body=UserModel)
        def handler(req: HttpRequest, body: UserModel) -> ResponseModel:
            return ResponseModel(message="ok")

        request = mock_request_factory(body=b'{"name": "ab", "age": 30}')
        response = handler(request)

        assert response.status_code == 422

        data = json.loads(response.get_body().decode())
        assert "detail" in data
        assert any(
            error["type"] in ["string_too_short", "too_small", "number_too_large", "too_large"]
            for error in data["detail"]
        )

    def test_query_validation_error(self, mock_request_factory):
        """Test 422 error for invalid query params."""

        @validate_http(query=QueryModel)
        def handler(req: HttpRequest, query: QueryModel) -> ResponseModel:
            return ResponseModel(message="ok")

        request = mock_request_factory(params={"limit": "0"})
        response = handler(request)

        assert response.status_code == 422

        data = json.loads(response.get_body().decode())
        assert "detail" in data

    def test_path_validation_error(self, mock_request_factory):
        """Test 422 error for invalid path params."""

        @validate_http(path=PathModel)
        def handler(req: HttpRequest, path: PathModel) -> ResponseModel:
            return ResponseModel(message="ok")

        request = mock_request_factory(route_params={"user_id": "0"})
        response = handler(request)

        assert response.status_code == 422

        data = json.loads(response.get_body().decode())
        assert "detail" in data

    def test_headers_validation_error(self, mock_request_factory):
        """Test 422 error for invalid headers."""

        @validate_http(headers=HeaderModel)
        def handler(req: HttpRequest, headers: HeaderModel) -> ResponseModel:
            return ResponseModel(message="ok")

        request = mock_request_factory()
        response = handler(request)

        assert response.status_code == 422

        data = json.loads(response.get_body().decode())
        assert "detail" in data

    def test_json_parsing_error(self, mock_request_factory):
        """Test 400 error for malformed JSON."""

        @validate_http(body=UserModel)
        def handler(req: HttpRequest, body: UserModel) -> ResponseModel:
            return ResponseModel(message="ok")

        request = mock_request_factory(body=b"invalid json")
        response = handler(request)

        assert response.status_code == 400

        data = json.loads(response.get_body().decode())
        assert "detail" in data

    def test_all_validation_sources(self, mock_request_factory):
        """Test validation of all input sources at once."""

        @validate_http(body=UserModel, query=QueryModel, path=PathModel, headers=HeaderModel)
        def handler(
            req: HttpRequest,
            body: UserModel,
            query: QueryModel,
            path: PathModel,
            headers: HeaderModel,
        ) -> ResponseModel:
            return ResponseModel(message="ok")

        request = mock_request_factory(
            body=b'{"name": "Eve", "age": 27}',
            params={"limit": "5"},
            route_params={"user_id": "100"},
        )
        request.headers = {"authorization": "Bearer token123", "user_agent": "Mozilla"}
        response = handler(request)

        assert response.status_code == 200

    @pytest.mark.skip("Error location format varies by Pydantic version")
    def test_validation_error_location(self, mock_request_factory):
        """Test that error location is correctly reported."""

        @validate_http(body=UserModel)
        def handler(req: HttpRequest, body: UserModel) -> ResponseModel:
            return ResponseModel(message="ok")

        request = mock_request_factory(body=b'{"age": 30}')
        response = handler(request)

        assert response.status_code == 422

        data = json.loads(response.get_body().decode())
        assert any("name" in str(error.get("loc", [])) for error in data["detail"])


class TestConfigurationErrors:
    """Tests for decorator configuration errors."""

    def test_request_model_with_body_conflict(self):
        """Test ValueError when request_model and body are both provided."""

        with pytest.raises(
            ValueError, match="Cannot use request_model together with body/query/path/headers"
        ):

            @validate_http(request_model=UserModel, body=UserModel)
            def handler(req: HttpRequest):
                pass

    @pytest.mark.skip("Async handler support requires further investigation")
    def test_async_handler(self, mock_request_factory):
        """Test async handler support."""

        import asyncio

        @validate_http(body=UserModel)
        async def async_handler(req: HttpRequest, body: UserModel) -> ResponseModel:
            return ResponseModel(message=f"Hello, {body.name}")

        request = mock_request_factory(body=b'{"name": "Lucas", "age": 32}')
        response = asyncio.run(async_handler(request))

        assert response.status_code == 200

    def test_httprequest_injectable(self, mock_request_factory):
        """Test that original HttpRequest can be accessed."""

        @validate_http(body=UserModel)
        def handler(req: HttpRequest, body: UserModel, http_request: HttpRequest) -> ResponseModel:
            user_agent = http_request.headers.get("User-Agent", "unknown")
            return ResponseModel(message=f"Hello, {body.name} (UA: {user_agent})")

        request = mock_request_factory(body=b'{"name": "Mia", "age": 24}')
        response = handler(request)

        assert response.status_code == 200

        data = json.loads(response.get_body().decode())
        assert "UA:" in data["message"]


# Test custom error formatter
class TestCustomErrorFormatter:
    """Tests for custom error formatter functionality."""

    def test_custom_formatter_for_validation_error(self, mock_request_factory):
        """Test custom error formatter for validation errors."""

        def custom_formatter(exc: Exception, status_code: int) -> dict:
            return {
                "custom": True,
                "code": f"ERR_{status_code}",
                "message": str(exc),
            }

        @validate_http(body=UserModel, error_formatter=custom_formatter)
        def handler(req: HttpRequest, body: UserModel) -> dict:
            return {"message": "ok"}

        request = mock_request_factory(body=b'{"name": "ab", "age": 30}')
        response = handler(request)

        assert response.status_code == 422

        data = json.loads(response.get_body().decode())
        assert data["custom"] is True
        assert data["code"] == "ERR_422"
        assert "string_too_short" in data["message"] or "min_length" in data["message"]

    def test_custom_formatter_for_json_error(self, mock_request_factory):
        """Test custom error formatter for JSON parsing errors."""

        def custom_formatter(exc: Exception, status_code: int) -> dict:
            return {
                "error": "JSON_ERROR",
                "status": status_code,
                "details": str(exc),
            }

        @validate_http(body=UserModel, error_formatter=custom_formatter)
        def handler(req: HttpRequest, body: UserModel) -> dict:
            return {"message": "ok"}

        request = mock_request_factory(body=b"invalid json")
        response = handler(request)

        assert response.status_code == 400

        data = json.loads(response.get_body().decode())
        assert data["error"] == "JSON_ERROR"
        assert data["status"] == 400

    def test_default_formatter_when_not_provided(self, mock_request_factory):
        """Test default FastAPI-style formatter when custom formatter not provided."""

        @validate_http(body=UserModel)
        def handler(req: HttpRequest, body: UserModel) -> dict:
            return {"message": "ok"}

        request = mock_request_factory(body=b'{"name": "ab", "age": 30}')
        response = handler(request)

        assert response.status_code == 422

        data = json.loads(response.get_body().decode())
        assert "detail" in data
        assert len(data["detail"]) > 0
        assert "loc" in data["detail"][0]
        assert "msg" in data["detail"][0]
        assert "type" in data["detail"][0]

    def test_custom_formatter_for_response_validation_error(self, mock_request_factory):
        """Test custom error formatter for response validation errors."""

        def custom_formatter(exc: Exception, status_code: int) -> dict:
            return {
                "error_type": "CONTRACT_VIOLATION",
                "http_status": status_code,
            }

        class ResponseModel(BaseModel):
            message: str

        @validate_http(
            body=UserModel,
            response_model=ResponseModel,
            error_formatter=custom_formatter,
        )
        def handler(req: HttpRequest, body: UserModel) -> dict:
            return {"invalid": "data"}

        request = mock_request_factory(body=b'{"name": "Frank", "age": 40}')
        response = handler(request)

        assert response.status_code == 500

        data = json.loads(response.get_body().decode())
        assert data["error_type"] == "CONTRACT_VIOLATION"
        assert data["http_status"] == 500


# Test global error handlers
class TestGlobalErrorHandlers:
    """Tests for global error handler registration."""

    def setup_method(self):
        """Clear global handlers before each test."""
        from azure_functions_validation import clear_global_error_handlers

        clear_global_error_handlers()

    def teardown_method(self):
        """Clear global handlers after each test."""
        from azure_functions_validation import clear_global_error_handlers

        clear_global_error_handlers()

    def test_global_handler_for_validation_error(self, mock_request_factory):
        """Test global error handler for validation errors."""

        from azure_functions_validation import register_global_error_handler

        def global_handler(exc: Exception) -> HttpResponse:
            return HttpResponse(
                body=json.dumps({"global": True, "message": str(exc)}),
                status_code=422,
                headers={"Content-Type": "application/json"},
            )

        register_global_error_handler(Exception, global_handler)

        @validate_http(body=UserModel)
        def handler(req: HttpRequest, body: UserModel) -> dict:
            return {"message": "ok"}

        request = mock_request_factory(body=b'{"name": "ab", "age": 30}')
        response = handler(request)

        assert response.status_code == 422

        data = json.loads(response.get_body().decode())
        assert data["global"] is True

    def test_endpoint_specific_overrides_global(self, mock_request_factory):
        """Test endpoint-specific error formatter overrides global handler."""

        from azure_functions_validation import register_global_error_handler

        def global_handler(exc: Exception) -> HttpResponse:
            return HttpResponse(
                body=json.dumps({"source": "global"}),
                status_code=422,
                headers={"Content-Type": "application/json"},
            )

        def endpoint_formatter(exc: Exception, status_code: int) -> dict:
            return {"source": "endpoint"}

        register_global_error_handler(Exception, global_handler)

        @validate_http(body=UserModel, error_formatter=endpoint_formatter)
        def handler(req: HttpRequest, body: UserModel) -> dict:
            return {"message": "ok"}

        request = mock_request_factory(body=b'{"name": "ab", "age": 30}')
        response = handler(request)

        assert response.status_code == 422

        data = json.loads(response.get_body().decode())
        assert data["source"] == "endpoint"

    def test_global_handler_precedence_with_default(self, mock_request_factory):
        """Test that global handlers work when no endpoint-specific formatter is provided."""

        from pydantic import ValidationError as PydanticValidationError

        from azure_functions_validation import register_global_error_handler

        def global_handler(exc: Exception) -> HttpResponse:
            return HttpResponse(
                body=json.dumps({"handled": "globally"}),
                status_code=422,
                headers={"Content-Type": "application/json"},
            )

        register_global_error_handler(PydanticValidationError, global_handler)

        @validate_http(body=UserModel)
        def handler(req: HttpRequest, body: UserModel) -> dict:
            return {"message": "ok"}

        request = mock_request_factory(body=b'{"name": "ab", "age": 30}')
        response = handler(request)

        assert response.status_code == 422

        data = json.loads(response.get_body().decode())
        assert data["handled"] == "globally"

    def test_clear_global_handlers(self):
        """Test clearing all global error handlers."""

        from azure_functions_validation import (
            clear_global_error_handlers,
            register_global_error_handler,
        )

        def dummy_handler(exc: Exception) -> HttpResponse:
            return HttpResponse("dummy")

        register_global_error_handler(Exception, dummy_handler)

        from azure_functions_validation.registry import GlobalErrorHandlerRegistry

        initial_count = len(GlobalErrorHandlerRegistry._handlers)
        assert initial_count > 0

        clear_global_error_handlers()

        final_count = len(GlobalErrorHandlerRegistry._handlers)
        assert final_count == 0


# Test OpenAPI integration utilities
class TestOpenAPIIntegration:
    """Tests for OpenAPI integration utilities."""

    def test_generate_422_error_schema(self):
        """Test 422 error schema generation."""

        from azure_functions_validation import generate_422_error_schema

        schema = generate_422_error_schema(UserModel)

        assert schema["type"] == "object"
        assert "properties" in schema
        assert "detail" in schema["properties"]
        assert schema["properties"]["detail"]["type"] == "array"
        assert schema["properties"]["detail"]["items"]["type"] == "object"
        assert "loc" in schema["properties"]["detail"]["items"]["properties"]
        assert "msg" in schema["properties"]["detail"]["items"]["properties"]
        assert "type" in schema["properties"]["detail"]["items"]["properties"]

    def test_get_validation_error_examples(self):
        """Test validation error examples generation."""

        from azure_functions_validation import get_validation_error_examples

        examples = get_validation_error_examples(UserModel)

        assert isinstance(examples, list)
        assert len(examples) > 0

        for example in examples:
            assert "value" in example
            assert "detail" in example["value"]
            assert isinstance(example["value"]["detail"], list)

    def test_schema_structure_compatibility(self):
        """Test that generated schema is compatible with OpenAPI spec."""

        from azure_functions_validation import generate_422_error_schema

        schema = generate_422_error_schema(UserModel)

        required_keys = {"type", "properties"}
        assert all(key in schema for key in required_keys)
        assert schema["properties"]["detail"]["type"] == "array"
        assert schema["properties"]["detail"]["items"]["type"] == "object"
