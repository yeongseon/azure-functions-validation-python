"""Tests for validation adapter."""

from pydantic import BaseModel, Field
from pydantic import ValidationError as PydanticValidationError
import pytest

from azure_functions_validation.adapter import PydanticAdapter


# Test models
class UserModel(BaseModel):
    """Test model for user data."""

    name: str = Field(min_length=3, max_length=50)
    age: int = Field(ge=0, le=150)


class SimpleModel(BaseModel):
    """Simple test model."""

    message: str


# Fixtures
@pytest.fixture
def adapter() -> PydanticAdapter:
    """Create a PydanticAdapter instance."""
    return PydanticAdapter()


@pytest.fixture
def mock_request() -> type:
    """Create a mock HttpRequest class for testing."""

    class MockHttpRequest:
        """Mock Azure Functions HttpRequest."""

        def __init__(self, body: bytes = b""):
            self._body = body

        def get_body(self) -> bytes:
            return self._body

    return MockHttpRequest


# Test parse_body
class TestParseBody:
    """Tests for parse_body method."""

    def test_valid_json_body(self, adapter: PydanticAdapter, mock_request: type) -> None:
        """Test parsing valid JSON body."""
        req = mock_request(b'{"name": "Alice", "age": 30}')
        result = adapter.parse_body(req, UserModel)

        assert isinstance(result, UserModel)
        assert result.name == "Alice"
        assert result.age == 30

    def test_empty_body(self, adapter: PydanticAdapter, mock_request: type) -> None:
        """Test parsing empty body raises ValidationError with type='missing'."""
        req = mock_request(b"")

        with pytest.raises(PydanticValidationError) as exc_info:
            adapter.parse_body(req, UserModel)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "missing"
        assert errors[0]["loc"] == ("body",)

    def test_invalid_json(self, adapter: PydanticAdapter, mock_request: type) -> None:
        """Test parsing invalid JSON raises ValueError."""
        req = mock_request(b"{invalid json}")

        with pytest.raises(ValueError) as exc_info:
            adapter.parse_body(req, UserModel)

        assert "Invalid JSON" in str(exc_info.value)

    def test_validation_error_field_constraints(
        self, adapter: PydanticAdapter, mock_request: type
    ) -> None:
        """Test validation errors for field constraints."""
        # Name too short
        req = mock_request(b'{"name": "Al", "age": 30}')
        with pytest.raises(PydanticValidationError) as exc_info:
            adapter.parse_body(req, UserModel)

        errors = exc_info.value.errors()
        assert any(e["type"] == "string_too_short" for e in errors)

    def test_validation_error_missing_field(
        self, adapter: PydanticAdapter, mock_request: type
    ) -> None:
        """Test validation errors for missing required field."""
        req = mock_request(b'{"name": "Alice"}')
        with pytest.raises(PydanticValidationError) as exc_info:
            adapter.parse_body(req, UserModel)

        errors = exc_info.value.errors()
        assert any(e["type"] == "missing" for e in errors)

    def test_validation_error_wrong_type(
        self, adapter: PydanticAdapter, mock_request: type
    ) -> None:
        """Test validation errors for wrong field type."""
        req = mock_request(b'{"name": "Alice", "age": "not a number"}')
        with pytest.raises(PydanticValidationError) as exc_info:
            adapter.parse_body(req, UserModel)

        errors = exc_info.value.errors()
        assert any("int_parsing" in e["type"] for e in errors)


# Test validate_response
class TestValidateResponse:
    """Tests for validate_response method."""

    def test_validate_basemodel_instance(self, adapter: PydanticAdapter) -> None:
        """Test validating BaseModel instance."""
        user = UserModel(name="Alice", age=30)
        result = adapter.validate_response(user, UserModel)

        assert result is user
        assert isinstance(result, UserModel)

    def test_validate_dict(self, adapter: PydanticAdapter) -> None:
        """Test validating dict against model."""
        data = {"name": "Bob", "age": 25}
        result = adapter.validate_response(data, UserModel)

        assert isinstance(result, UserModel)
        assert result.name == "Bob"
        assert result.age == 25

    def test_validate_dict_invalid(self, adapter: PydanticAdapter) -> None:
        """Test validating invalid dict raises ValidationError."""
        data = {"name": "Al", "age": 25}  # Name too short

        with pytest.raises(PydanticValidationError) as exc_info:
            adapter.validate_response(data, UserModel)

        errors = exc_info.value.errors()
        assert any(e["type"] == "string_too_short" for e in errors)

    def test_validate_invalid_type(self, adapter: PydanticAdapter) -> None:
        """Test validating invalid response type raises TypeError."""
        with pytest.raises(TypeError) as exc_info:
            adapter.validate_response("invalid", UserModel)

        assert "Expected UserModel, dict, or list, got str" in str(exc_info.value)


# Test serialize
class TestSerialize:
    """Tests for serialize method."""

    def test_serialize_basemodel(self, adapter: PydanticAdapter) -> None:
        """Test serializing BaseModel instance."""
        user = UserModel(name="Alice", age=30)
        content, content_type = adapter.serialize(user)

        assert content_type == "application/json"
        assert '"name":"Alice"' in content or '"name": "Alice"' in content
        assert '"age":30' in content or '"age": 30' in content

    def test_serialize_dict(self, adapter: PydanticAdapter) -> None:
        """Test serializing dict."""
        data = {"key": "value", "number": 42}
        content, content_type = adapter.serialize(data)

        assert content_type == "application/json"
        assert '"key":"value"' in content or '"key": "value"' in content
        assert '"number":42' in content or '"number": 42' in content

    def test_serialize_list(self, adapter: PydanticAdapter) -> None:
        """Test serializing list."""
        data = [1, 2, 3, "test"]
        content, content_type = adapter.serialize(data)

        assert content_type == "application/json"
        assert "[1" in content or '["test"]' in content

    def test_serialize_string(self, adapter: PydanticAdapter) -> None:
        """Test serializing string."""
        data = "Hello, World!"
        content, content_type = adapter.serialize(data)

        assert content_type == "text/plain; charset=utf-8"
        assert content == "Hello, World!"

    def test_serialize_bytes(self, adapter: PydanticAdapter) -> None:
        """Test serializing bytes."""
        data = b"binary data"
        content, content_type = adapter.serialize(data)

        assert content_type == "application/octet-stream"
        assert content == b"binary data"

    def test_serialize_invalid_type(self, adapter: PydanticAdapter) -> None:
        """Test serializing invalid type raises TypeError."""
        with pytest.raises(TypeError) as exc_info:
            adapter.serialize(object())

        assert "Cannot serialize type" in str(exc_info.value)


# Test format_error
class TestFormatError:
    """Tests for format_error method."""

    def test_format_validation_error(self, adapter: PydanticAdapter, mock_request: type) -> None:
        """Test formatting ValidationError."""
        req = mock_request(b'{"name": "Al", "age": 30}')
        try:
            adapter.parse_body(req, UserModel)
        except PydanticValidationError as e:
            result = adapter.format_error(e)

            assert "detail" in result
            assert isinstance(result["detail"], list)
            assert len(result["detail"]) > 0

            error = result["detail"][0]
            assert "loc" in error
            assert "msg" in error
            assert "type" in error

    def test_format_generic_exception(self, adapter: PydanticAdapter) -> None:
        """Test formatting generic exception."""
        exc = Exception("Something went wrong")
        result = adapter.format_error(exc)

        assert "detail" in result
        assert isinstance(result["detail"], list)
        assert len(result["detail"]) == 1

        error = result["detail"][0]
        assert error["loc"] == []
        assert error["msg"] == "Something went wrong"
        assert error["type"] == "value_error"


# Test error type mapping
class TestErrorTypeMapping:
    """Tests for _map_error_type method."""

    def test_missing_type(self, adapter: PydanticAdapter) -> None:
        """Test mapping 'missing' type."""
        assert adapter._map_error_type("missing") == "missing"
        assert adapter._map_error_type("missing_required") == "missing"

    def test_string_types(self, adapter: PydanticAdapter) -> None:
        """Test mapping string validation types."""
        assert adapter._map_error_type("string_too_short") == "string_too_short"
        assert adapter._map_error_type("string_too_long") == "string_too_long"

    def test_number_types(self, adapter: PydanticAdapter) -> None:
        """Test mapping number validation types."""
        assert adapter._map_error_type("greater_than") == "number_too_large"
        assert adapter._map_error_type("greater_than_equal") == "number_too_large"
        assert adapter._map_error_type("too_large") == "number_too_large"
        assert adapter._map_error_type("less_than") == "number_too_small"
        assert adapter._map_error_type("less_than_equal") == "number_too_small"
        assert adapter._map_error_type("too_small") == "number_too_small"

    def test_type_error_pattern(self, adapter: PydanticAdapter) -> None:
        """Test mapping type_error.* patterns."""
        assert adapter._map_error_type("type_error") == "invalid_type"
        assert adapter._map_error_type("type_error.integer") == "invalid_type"
        assert adapter._map_error_type("type_error.str") == "invalid_type"

    def test_value_error_pattern(self, adapter: PydanticAdapter) -> None:
        """Test mapping value_error.* patterns."""
        assert adapter._map_error_type("value_error") == "value_error"
        assert adapter._map_error_type("value_error.any_str.min_length") == "value_error"

    def test_unknown_type(self, adapter: PydanticAdapter) -> None:
        """Test mapping unknown types defaults to value_error."""
        assert adapter._map_error_type("some_unknown_type") == "value_error"
        assert adapter._map_error_type("custom_error") == "value_error"
