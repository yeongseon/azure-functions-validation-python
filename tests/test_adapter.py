"""Unit tests for the PydanticAdapter."""
import pytest
from azure.functions import HttpRequest
from pydantic import BaseModel, ValidationError

from azure_functions_validation._adapter import PydanticAdapter


class QueryModel(BaseModel):
    name: str
    age: int


def test_parse_query_success():
    adapter = PydanticAdapter()
    req = HttpRequest(
        method="GET",
        url="/",
        params={"name": "Jane", "age": "25"},
        body=None
    )
    model = adapter.parse_query(req, QueryModel)
    assert model.name == "Jane"
    assert model.age == 25

def test_parse_query_validation_error():
    adapter = PydanticAdapter()
    req = HttpRequest(
        method="GET",
        url="/",
        params={"name": "Jane"}, # Missing age
        body=None
    )
    with pytest.raises(ValidationError):
        adapter.parse_query(req, QueryModel)

def test_parse_path_success():
    adapter = PydanticAdapter()
    req = HttpRequest(
        method="GET",
        url="/users/John/30",
        route_params={"name": "John", "age": "30"},
        body=None
    )
    model = adapter.parse_path(req, QueryModel)
    assert model.name == "John"
    assert model.age == 30

def test_parse_headers_success():
    adapter = PydanticAdapter()
    req = HttpRequest(
        method="GET",
        url="/",
        headers={"name": "HeaderName", "age": "40"},
        body=None
    )
    model = adapter.parse_headers(req, QueryModel)
    assert model.name == "HeaderName"
    assert model.age == 40