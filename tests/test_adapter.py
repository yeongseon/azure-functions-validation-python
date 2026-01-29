"""Unit tests for the PydanticAdapter."""
import pytest
from pydantic import BaseModel, ValidationError

from azure_functions_validation._adapter import PydanticAdapter


class SimpleModel(BaseModel):
    name: str


def test_validate_response_list_success():
    adapter = PydanticAdapter()
    data = [{"name": "Test1"}, {"name": "Test2"}]
    
    validated_data = adapter.validate_response(data, list[SimpleModel])
    
    assert isinstance(validated_data, list)
    assert len(validated_data) == 2
    assert isinstance(validated_data[0], SimpleModel)
    assert validated_data[0].name == "Test1"

def test_validate_response_list_fails():
    adapter = PydanticAdapter()
    data = [{"name": "Test1"}, {"wrong_field": "Test2"}] # Second item is invalid
    
    with pytest.raises(ValidationError):
        adapter.validate_response(data, list[SimpleModel])