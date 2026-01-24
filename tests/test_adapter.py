"""Tests for the validation adapter."""

from unittest.mock import Mock

from pydantic import BaseModel, Field, ValidationError
import pytest

from azure_functions_validation._adapter import PydanticAdapter


# Test models
class SimpleModel(BaseModel):
    """Simple test model."""

    name: str
    age: int


class StringConstraintModel(BaseModel):
    """Model with string constraints."""

    short: str = Field(min_length=3)
    long: str = Field(max_length=10)


class NumberConstraintModel(BaseModel):
    """Model with number constraints."""

    min_val: int = Field(ge=10)
    max_val: int = Field(le=100)


class ResponseModel(BaseModel):
    """Response model for testing."""

    message: str
    status: str = "ok"


# Test parse_body
class TestParseBody:
    """Tests for parse_body method."""

    def test_parse_valid_json(self, adapter: PydanticAdapter, mock_request: Mock) -> None:
        """Test parsing valid JSON body."""
        mock_request.get_body.return_value = b'{"name": "John", "age": 30}'
        mock_request.get_json.return_value = {"name": "John", "age": 30}

        result = adapter.parse_body(mock_request, SimpleModel)

        assert isinstance(result, SimpleModel)
        assert result.name == "John"
        assert result.age == 30

    def test_parse_empty_body(self, adapter: PydanticAdapter, mock_request: Mock) -> None:
        """Test parsing empty body raises ValidationError with type='missing'."""
        mock_request.get_body.return_value = b""

        with pytest.raises(ValidationError) as exc_info:
            adapter.parse_body(mock_request, SimpleModel)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "missing"
        assert errors[0]["loc"] == ("body",)

    def test_parse_invalid_json(self, adapter: PydanticAdapter, mock_request: Mock) -> None:
        """Test parsing invalid JSON raises ValueError with 'Invalid JSON' message."""
        mock_request.get_body.return_value = b'{"invalid": json}'
        mock_request.get_json.side_effect = ValueError("Invalid JSON")

        with pytest.raises(ValueError, match="Invalid JSON"):
            adapter.parse_body(mock_request, SimpleModel)

    def test_parse_validation_error(self, adapter: PydanticAdapter, mock_request: Mock) -> None:
        """Test validation error on invalid data."""
        mock_request.get_body.return_value = b'{"name": "John"}'
        mock_request.get_json.return_value = {"name": "John"}  # missing 'age'

        with pytest.raises(ValidationError) as exc_info:
            adapter.parse_body(mock_request, SimpleModel)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("age",) for e in errors)


# Test validate_response
class TestValidateResponse:
    """Tests for validate_response method."""

    def test_validate_basemodel_instance(self, adapter: PydanticAdapter) -> None:
        """Test validating BaseModel instance."""
        model_instance = ResponseModel(message="Hello", status="success")

        result = adapter.validate_response(model_instance, ResponseModel)

        assert isinstance(result, ResponseModel)
        assert result.message == "Hello"
        assert result.status == "success"

    def test_validate_dict(self, adapter: PydanticAdapter) -> None:
        """Test validating dict."""
        data = {"message": "Hello", "status": "success"}

        result = adapter.validate_response(data, ResponseModel)

        assert isinstance(result, ResponseModel)
        assert result.message == "Hello"
        assert result.status == "success"

    def test_validate_dict_with_defaults(self, adapter: PydanticAdapter) -> None:
        """Test validating dict with default values."""
        data = {"message": "Hello"}

        result = adapter.validate_response(data, ResponseModel)

        assert isinstance(result, ResponseModel)
        assert result.message == "Hello"
        assert result.status == "ok"  # default value

    def test_validate_invalid_type(self, adapter: PydanticAdapter) -> None:
        """Test validating invalid type raises TypeError."""
        with pytest.raises(TypeError, match="Expected BaseModel or dict"):
            adapter.validate_response("invalid", ResponseModel)

    def test_validate_dict_missing_required_field(self, adapter: PydanticAdapter) -> None:
        """Test validating dict with missing required field."""
        data = {"status": "ok"}  # missing 'message'

        with pytest.raises(ValidationError) as exc_info:
            adapter.validate_response(data, ResponseModel)

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("message",) for e in errors)


# Test serialize
class TestSerialize:
    """Tests for serialize method."""

    def test_serialize_basemodel(self, adapter: PydanticAdapter) -> None:
        """Test serializing BaseModel instance."""
        model_instance = ResponseModel(message="Hello", status="success")

        content, content_type = adapter.serialize(model_instance)

        assert content_type == "application/json"
        assert isinstance(content, str)
        assert "Hello" in content
        assert "success" in content

    def test_serialize_dict(self, adapter: PydanticAdapter) -> None:
        """Test serializing dict."""
        data = {"message": "Hello", "status": "success"}

        content, content_type = adapter.serialize(data)

        assert content_type == "application/json"
        assert isinstance(content, str)
        assert "Hello" in content
        assert "success" in content

    def test_serialize_list(self, adapter: PydanticAdapter) -> None:
        """Test serializing list."""
        data = [1, 2, 3, 4, 5]

        content, content_type = adapter.serialize(data)

        assert content_type == "application/json"
        assert isinstance(content, str)
        assert "[1, 2, 3, 4, 5]" in content or "[1,2,3,4,5]" in content

    def test_serialize_string(self, adapter: PydanticAdapter) -> None:
        """Test serializing string."""
        data = "Plain text response"

        content, content_type = adapter.serialize(data)

        assert content_type == "text/plain; charset=utf-8"
        assert content == "Plain text response"

    def test_serialize_bytes(self, adapter: PydanticAdapter) -> None:
        """Test serializing bytes."""
        data = b"Binary data"

        content, content_type = adapter.serialize(data)

        assert content_type == "application/octet-stream"
        assert content == b"Binary data"

    def test_serialize_invalid_type(self, adapter: PydanticAdapter) -> None:
        """Test serializing invalid type raises TypeError."""
        with pytest.raises(TypeError, match="Cannot serialize type"):
            adapter.serialize(object())


# Test format_error
class TestFormatError:
    """Tests for format_error method."""

    def test_format_validation_error(self, adapter: PydanticAdapter) -> None:
        """Test formatting ValidationError."""
        try:
            SimpleModel(name="John")  # type: ignore[call-arg]
        except ValidationError as exc:
            result = adapter.format_error(exc)

        assert "detail" in result
        assert isinstance(result["detail"], list)
        assert len(result["detail"]) > 0
        assert "loc" in result["detail"][0]
        assert "msg" in result["detail"][0]
        assert "type" in result["detail"][0]

    def test_format_generic_exception(self, adapter: PydanticAdapter) -> None:
        """Test formatting generic exception."""
        exc = ValueError("Something went wrong")

        result = adapter.format_error(exc)

        assert "detail" in result
        assert isinstance(result["detail"], list)
        assert len(result["detail"]) == 1
        assert result["detail"][0]["loc"] == ["body"]
        assert result["detail"][0]["msg"] == "Something went wrong"
        assert result["detail"][0]["type"] == "value_error"


# Test error type mapping
class TestErrorTypeMapping:
    """Tests for error type mapping."""

    def test_map_missing_type(self, adapter: PydanticAdapter) -> None:
        """Test mapping of 'missing' type."""
        try:
            SimpleModel(name="John")  # type: ignore[call-arg]
        except ValidationError as exc:
            result = adapter.format_error(exc)

        # Should map to 'missing'
        assert any(e["type"] == "missing" for e in result["detail"])

    def test_map_string_too_short(self, adapter: PydanticAdapter) -> None:
        """Test mapping of 'string_too_short' type."""
        try:
            StringConstraintModel(short="ab", long="valid")
        except ValidationError as exc:
            result = adapter.format_error(exc)

        # Should preserve 'string_too_short'
        assert any(e["type"] == "string_too_short" for e in result["detail"])

    def test_map_string_too_long(self, adapter: PydanticAdapter) -> None:
        """Test mapping of 'string_too_long' type."""
        try:
            StringConstraintModel(short="valid", long="this is too long")
        except ValidationError as exc:
            result = adapter.format_error(exc)

        # Should preserve 'string_too_long'
        assert any(e["type"] == "string_too_long" for e in result["detail"])

    def test_map_number_too_large(self, adapter: PydanticAdapter) -> None:
        """Test mapping of number constraint types to 'number_too_large'."""
        try:
            NumberConstraintModel(min_val=10, max_val=150)
        except ValidationError as exc:
            result = adapter.format_error(exc)

        # Should map to 'number_too_large'
        assert any(e["type"] == "number_too_large" for e in result["detail"])

    def test_map_number_too_small(self, adapter: PydanticAdapter) -> None:
        """Test mapping of number constraint types to 'number_too_small'."""
        try:
            NumberConstraintModel(min_val=5, max_val=50)
        except ValidationError as exc:
            result = adapter.format_error(exc)

        # Should map to 'number_too_small'
        assert any(e["type"] == "number_too_small" for e in result["detail"])

    def test_map_invalid_type(self, adapter: PydanticAdapter) -> None:
        """Test mapping of type errors to 'invalid_type'."""
        try:
            SimpleModel(name="John", age="not a number")  # type: ignore[arg-type]
        except ValidationError as exc:
            result = adapter.format_error(exc)

        # Should map to 'invalid_type'
        assert any(e["type"] == "invalid_type" for e in result["detail"])

    # Direct mapping tests
    # Note: Testing private method _map_error_type directly to ensure comprehensive coverage
    # of all error type mappings defined in the PRD. This is acceptable for critical mapping
    # logic that needs to be exhaustively tested.
    def test_direct_map_missing_type(self, adapter: PydanticAdapter) -> None:
        """Test direct mapping of 'missing' type."""
        assert adapter._map_error_type("missing") == "missing"
        assert adapter._map_error_type("missing_required") == "missing"

    def test_direct_map_string_types(self, adapter: PydanticAdapter) -> None:
        """Test direct mapping of string constraint types."""
        assert adapter._map_error_type("string_too_short") == "string_too_short"
        assert adapter._map_error_type("string_too_long") == "string_too_long"

    def test_direct_map_number_too_large(self, adapter: PydanticAdapter) -> None:
        """Test direct mapping of number too large types."""
        assert adapter._map_error_type("greater_than") == "number_too_large"
        assert adapter._map_error_type("less_than_equal") == "number_too_large"
        assert adapter._map_error_type("too_large") == "number_too_large"

    def test_direct_map_number_too_small(self, adapter: PydanticAdapter) -> None:
        """Test direct mapping of number too small types."""
        assert adapter._map_error_type("less_than") == "number_too_small"
        assert adapter._map_error_type("greater_than_equal") == "number_too_small"
        assert adapter._map_error_type("too_small") == "number_too_small"

    def test_direct_map_type_error(self, adapter: PydanticAdapter) -> None:
        """Test direct mapping of type error types."""
        assert adapter._map_error_type("type_error") == "invalid_type"
        assert adapter._map_error_type("type_error.integer") == "invalid_type"
        assert adapter._map_error_type("type_error.float") == "invalid_type"
        assert adapter._map_error_type("int_parsing") == "invalid_type"
        assert adapter._map_error_type("float_parsing") == "invalid_type"

    def test_direct_map_value_error(self, adapter: PydanticAdapter) -> None:
        """Test direct mapping of value error types."""
        assert adapter._map_error_type("value_error") == "value_error"
        assert adapter._map_error_type("value_error.any_str.min_length") == "value_error"

    def test_direct_map_unknown_type(self, adapter: PydanticAdapter) -> None:
        """Test direct mapping of unknown types defaults to 'value_error'."""
        assert adapter._map_error_type("unknown_type") == "value_error"
        assert adapter._map_error_type("some_other_error") == "value_error"
