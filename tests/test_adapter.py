"""Tests for the Pydantic adapter."""

import json

from azure.functions import HttpRequest
from pydantic import BaseModel, Field, ValidationError
import pytest

from azure_functions_validation._adapter import PydanticAdapter


class SampleModel(BaseModel):
    name: str
    age: int = Field(ge=0, le=120)


class TestPydanticAdapter:
    """Test PydanticAdapter functionality."""

    def test_parse_body_valid_json(self) -> None:
        """Test parsing valid JSON body."""
        adapter = PydanticAdapter()
        body_data = {"name": "Alice", "age": 30}
        req = HttpRequest(
            method="POST",
            url="http://localhost/test",
            body=json.dumps(body_data).encode(),
        )

        result = adapter.parse_body(req, SampleModel)

        assert isinstance(result, SampleModel)
        assert result.name == "Alice"
        assert result.age == 30

    def test_parse_body_empty_raises_validation_error(self) -> None:
        """Test parsing empty body raises ValidationError."""
        adapter = PydanticAdapter()
        req = HttpRequest(
            method="POST",
            url="http://localhost/test",
            body=b"",
        )

        with pytest.raises(ValidationError) as exc_info:
            adapter.parse_body(req, SampleModel)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "missing"
        assert errors[0]["loc"] == ("body",)

    def test_parse_body_invalid_json_raises_value_error(self) -> None:
        """Test parsing invalid JSON raises ValueError."""
        adapter = PydanticAdapter()
        req = HttpRequest(
            method="POST",
            url="http://localhost/test",
            body=b"{invalid json}",
        )

        with pytest.raises(ValueError, match="Invalid JSON"):
            adapter.parse_body(req, SampleModel)

    def test_parse_body_validation_error(self) -> None:
        """Test parsing body with validation error."""
        adapter = PydanticAdapter()
        body_data = {"name": "Bob", "age": 150}  # age > 120
        req = HttpRequest(
            method="POST",
            url="http://localhost/test",
            body=json.dumps(body_data).encode(),
        )

        with pytest.raises(ValidationError) as exc_info:
            adapter.parse_body(req, SampleModel)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "age" in str(errors[0]["loc"])

    def test_validate_response_with_model_instance(self) -> None:
        """Test validating response with model instance."""
        adapter = PydanticAdapter()
        model_instance = SampleModel(name="Charlie", age=25)

        result = adapter.validate_response(model_instance, SampleModel)

        assert result is model_instance

    def test_validate_response_with_dict(self) -> None:
        """Test validating response with dict."""
        adapter = PydanticAdapter()
        data = {"name": "Diana", "age": 35}

        result = adapter.validate_response(data, SampleModel)

        assert isinstance(result, SampleModel)
        assert result.name == "Diana"
        assert result.age == 35

    def test_validate_response_invalid_type_raises_error(self) -> None:
        """Test validating response with invalid type raises TypeError."""
        adapter = PydanticAdapter()

        with pytest.raises(TypeError, match="Cannot validate response"):
            adapter.validate_response("invalid", SampleModel)

    def test_serialize_model_instance(self) -> None:
        """Test serializing model instance."""
        adapter = PydanticAdapter()
        model = SampleModel(name="Eve", age=40)

        content, content_type = adapter.serialize(model)

        assert content_type == "application/json"
        parsed = json.loads(content)
        assert parsed["name"] == "Eve"
        assert parsed["age"] == 40

    def test_serialize_dict(self) -> None:
        """Test serializing dict."""
        adapter = PydanticAdapter()
        data = {"key": "value", "number": 42}

        content, content_type = adapter.serialize(data)

        assert content_type == "application/json"
        parsed = json.loads(content)
        assert parsed == data

    def test_serialize_list(self) -> None:
        """Test serializing list."""
        adapter = PydanticAdapter()
        data = [1, 2, 3, 4, 5]

        content, content_type = adapter.serialize(data)

        assert content_type == "application/json"
        parsed = json.loads(content)
        assert parsed == data

    def test_serialize_str(self) -> None:
        """Test serializing string."""
        adapter = PydanticAdapter()
        text = "Hello, World!"

        content, content_type = adapter.serialize(text)

        assert content == text
        assert content_type == "text/plain; charset=utf-8"

    def test_serialize_bytes(self) -> None:
        """Test serializing bytes."""
        adapter = PydanticAdapter()
        data = b"binary data"

        content, content_type = adapter.serialize(data)

        assert content == data
        assert content_type == "application/octet-stream"

    def test_serialize_invalid_type_raises_error(self) -> None:
        """Test serializing invalid type raises TypeError."""
        adapter = PydanticAdapter()

        with pytest.raises(TypeError, match="Cannot serialize"):
            adapter.serialize(object())

    def test_format_error_validation_error(self) -> None:
        """Test formatting ValidationError."""
        adapter = PydanticAdapter()

        # Create a validation error
        try:
            SampleModel(name="Test", age=-5)  # Invalid age
        except ValidationError as e:
            error_dict = adapter.format_error(e)

            assert "detail" in error_dict
            assert isinstance(error_dict["detail"], list)
            assert len(error_dict["detail"]) > 0
            error = error_dict["detail"][0]
            assert "loc" in error
            assert "msg" in error
            assert "type" in error

    def test_format_error_generic_exception(self) -> None:
        """Test formatting generic exception."""
        adapter = PydanticAdapter()
        exc = Exception("Something went wrong")

        error_dict = adapter.format_error(exc)

        assert "detail" in error_dict
        assert isinstance(error_dict["detail"], list)
        assert len(error_dict["detail"]) == 1
        error = error_dict["detail"][0]
        assert error["loc"] == ["body"]
        assert "Something went wrong" in error["msg"]
        assert error["type"] == "value_error"

    def test_map_error_type_missing(self) -> None:
        """Test mapping missing error type."""
        adapter = PydanticAdapter()
        assert adapter._map_error_type("missing") == "missing"
        assert adapter._map_error_type("missing_required") == "missing"

    def test_map_error_type_string_length(self) -> None:
        """Test mapping string length error types."""
        adapter = PydanticAdapter()
        assert adapter._map_error_type("string_too_short") == "string_too_short"
        assert adapter._map_error_type("string_too_long") == "string_too_long"

    def test_map_error_type_number_range(self) -> None:
        """Test mapping number range error types."""
        adapter = PydanticAdapter()
        assert adapter._map_error_type("greater_than") == "number_too_large"
        assert adapter._map_error_type("greater_than_equal") == "number_too_large"
        assert adapter._map_error_type("too_large") == "number_too_large"
        assert adapter._map_error_type("less_than") == "number_too_small"
        assert adapter._map_error_type("less_than_equal") == "number_too_small"
        assert adapter._map_error_type("too_small") == "number_too_small"

    def test_map_error_type_with_prefix(self) -> None:
        """Test mapping error types with prefixes."""
        adapter = PydanticAdapter()
        assert adapter._map_error_type("type_error.integer") == "invalid_type"
        assert adapter._map_error_type("value_error.missing") == "value_error"

    def test_map_error_type_unmapped(self) -> None:
        """Test mapping unmapped error type defaults to value_error."""
        adapter = PydanticAdapter()
        assert adapter._map_error_type("unknown_error") == "value_error"
