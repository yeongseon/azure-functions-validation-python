"""Unit tests for the PydanticAdapter."""

import json

import pytest
from azure.functions import HttpRequest
from pydantic import BaseModel, ValidationError

from azure_functions_validation.adapter import PydanticAdapter
from azure_functions_validation.exceptions import ResponseValidationError


class SimpleModel(BaseModel):
    name: str
    age: int


def test_parse_body_success():
    adapter = PydanticAdapter()
    req = HttpRequest(method="POST", url="/", body=json.dumps({"name": "John", "age": 30}).encode())
    model = adapter.parse_body(req, SimpleModel)
    assert isinstance(model, SimpleModel)
    assert model.name == "John"


def test_parse_body_invalid_json_raises_value_error():
    adapter = PydanticAdapter()
    req = HttpRequest(method="POST", url="/", body=b"{'bad json")
    with pytest.raises(ValueError, match="Invalid JSON"):
        adapter.parse_body(req, SimpleModel)


def test_parse_body_validation_error():
    adapter = PydanticAdapter()
    req = HttpRequest(
        method="POST", url="/", body=json.dumps({"name": "John"}).encode()
    )  # Missing 'age'
    with pytest.raises(ValidationError):
        adapter.parse_body(req, SimpleModel)


def test_parse_query():
    adapter = PydanticAdapter()
    req = HttpRequest(method="GET", url="/", params={"name": "Jane", "age": "25"}, body=None)
    model = adapter.parse_query(req, SimpleModel)
    assert model.name == "Jane"
    assert model.age == 25


def test_validate_response_success():
    adapter = PydanticAdapter()
    data = {"name": "Test", "age": 100}
    model = adapter.validate_response(data, SimpleModel)
    assert model.name == "Test"


def test_validate_response_list_success():
    adapter = PydanticAdapter()
    data = [{"name": "Test", "age": 100}]
    model = adapter.validate_response(data, list[SimpleModel])
    assert len(model) == 1
    assert model[0].name == "Test"


def test_validate_response_raises_exception():
    adapter = PydanticAdapter()
    data = {"name": "Test"}  # Missing age
    with pytest.raises(ResponseValidationError):
        adapter.validate_response(data, SimpleModel)


def test_format_error_validation_error():
    adapter = PydanticAdapter()
    try:
        SimpleModel.model_validate({"name": "Test"})
    except ValidationError as e:
        error_resp = adapter.format_error(e, ("body",))
        assert "detail" in error_resp
        assert len(error_resp["detail"]) == 1
        detail = error_resp["detail"][0]
        assert detail["loc"] == ["body", "age"]
        assert detail["type"] == "missing"


def test_format_error_value_error():
    adapter = PydanticAdapter()
    exc = ValueError("Invalid JSON")
    error_resp = adapter.format_error(exc, ("body",))
    assert error_resp["detail"][0]["type"] == "json_invalid"
    assert error_resp["detail"][0]["loc"] == ["body"]


def test_format_error_response_validation_error():
    adapter = PydanticAdapter()
    try:
        raise ResponseValidationError("Response failed")
    except ResponseValidationError as e:
        # Simulate the underlying cause
        try:
            SimpleModel.model_validate({})
        except ValidationError as cause:
            e.__cause__ = cause
            error_resp = adapter.format_error(e, ("response",))
            assert error_resp["detail"][0]["loc"] == ["response", "name"]
            assert error_resp["detail"][0]["type"] == "missing"
