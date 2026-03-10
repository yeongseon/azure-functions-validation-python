"""Dedicated tests for OpenAPI integration utilities."""

from typing import List, Optional

from pydantic import BaseModel, Field

from azure_functions_validation.openapi import (
    generate_422_error_schema,
    get_validation_error_examples,
)


# Test models
class UserModel(BaseModel):
    """Model with required fields."""

    name: str = Field(min_length=3, max_length=50)
    age: int = Field(ge=0, le=150)


class OptionalFieldsModel(BaseModel):
    """Model with optional fields."""

    title: str
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class EmptyModel(BaseModel):
    """Model with no fields."""

    pass


class TestGenerate422ErrorSchema:
    """Tests for generate_422_error_schema."""

    def test_returns_valid_openapi_object_schema(self) -> None:
        """Schema top-level should be an object type."""
        schema = generate_422_error_schema(UserModel)
        assert schema["type"] == "object"
        assert "properties" in schema

    def test_detail_is_array_of_objects(self) -> None:
        """detail property should be an array of error objects."""
        schema = generate_422_error_schema(UserModel)
        detail = schema["properties"]["detail"]
        assert detail["type"] == "array"
        assert detail["items"]["type"] == "object"

    def test_error_object_has_required_fields(self) -> None:
        """Each error object should have loc, msg, and type properties."""
        schema = generate_422_error_schema(UserModel)
        props = schema["properties"]["detail"]["items"]["properties"]
        assert "loc" in props
        assert "msg" in props
        assert "type" in props

    def test_loc_is_array_of_strings(self) -> None:
        """loc should be typed as array of strings."""
        schema = generate_422_error_schema(UserModel)
        loc = schema["properties"]["detail"]["items"]["properties"]["loc"]
        assert loc["type"] == "array"
        assert loc["items"]["type"] == "string"

    def test_msg_is_string(self) -> None:
        """msg should be typed as string."""
        schema = generate_422_error_schema(UserModel)
        msg = schema["properties"]["detail"]["items"]["properties"]["msg"]
        assert msg["type"] == "string"

    def test_type_is_string(self) -> None:
        """type should be typed as string."""
        schema = generate_422_error_schema(UserModel)
        typ = schema["properties"]["detail"]["items"]["properties"]["type"]
        assert typ["type"] == "string"

    def test_schema_same_for_different_models(self) -> None:
        """Schema structure should be the same regardless of model (it's a fixed 422 format)."""
        schema1 = generate_422_error_schema(UserModel)
        schema2 = generate_422_error_schema(OptionalFieldsModel)
        assert schema1 == schema2


class TestGetValidationErrorExamples:
    """Tests for get_validation_error_examples."""

    def test_returns_list(self) -> None:
        """Should return a list."""
        examples = get_validation_error_examples(UserModel)
        assert isinstance(examples, list)

    def test_generates_example_per_field(self) -> None:
        """Should generate at least one example per model property."""
        examples = get_validation_error_examples(UserModel)
        # UserModel has 'name' and 'age' fields
        assert len(examples) >= 2

    def test_example_structure(self) -> None:
        """Each example should have summary and value with detail."""
        examples = get_validation_error_examples(UserModel)
        for example in examples:
            assert "summary" in example
            assert "value" in example
            assert "detail" in example["value"]
            assert isinstance(example["value"]["detail"], list)

    def test_example_error_detail_structure(self) -> None:
        """Each error in detail should have loc, msg, type."""
        examples = get_validation_error_examples(UserModel)
        for example in examples:
            for error in example["value"]["detail"]:
                assert "loc" in error
                assert "msg" in error
                assert "type" in error

    def test_example_error_type_is_missing(self) -> None:
        """Generated examples should use 'missing' error type."""
        examples = get_validation_error_examples(UserModel)
        for example in examples:
            for error in example["value"]["detail"]:
                assert error["type"] == "missing"

    def test_example_loc_starts_with_body(self) -> None:
        """Error location should start with 'body'."""
        examples = get_validation_error_examples(UserModel)
        for example in examples:
            for error in example["value"]["detail"]:
                assert error["loc"][0] == "body"

    def test_example_summary_contains_field_name(self) -> None:
        """Summary should reference the field name."""
        examples = get_validation_error_examples(UserModel)
        field_names = {"name", "age"}
        for example in examples:
            assert any(field_name in example["summary"] for field_name in field_names), (
                f"Summary '{example['summary']}' doesn't reference any field"
            )

    def test_optional_fields_included(self) -> None:
        """Optional fields should also generate examples."""
        examples = get_validation_error_examples(OptionalFieldsModel)
        # OptionalFieldsModel has title, description, tags — all show up as properties
        assert len(examples) >= 1

    def test_empty_model_returns_empty_list(self) -> None:
        """Model with no fields should return empty list."""
        examples = get_validation_error_examples(EmptyModel)
        assert examples == []
