import pytest
from pydantic import BaseModel, Field

from azure_functions_validation.metadata import get_validation_error_contract
from azure_functions_validation.openapi import (
    generate_422_error_schema,
    get_openapi_response_metadata,
    get_validation_error_examples,
)


class ExampleRequest(BaseModel):
    name: str = Field(min_length=3)
    age: int = Field(ge=18)


def test_generate_422_error_schema_matches_validation_contract() -> None:
    contract = get_validation_error_contract(ExampleRequest)
    assert contract is not None

    assert generate_422_error_schema(ExampleRequest) == contract["schema"]


def test_get_validation_error_examples_match_validation_contract() -> None:
    contract = get_validation_error_contract(ExampleRequest)
    assert contract is not None

    assert get_validation_error_examples(ExampleRequest) == contract["examples"]
    assert any(
        example["summary"] == "Missing required field: name" for example in contract["examples"]
    )
    assert any("too short" in example["summary"].lower() for example in contract["examples"])
    assert any("too small" in example["summary"].lower() for example in contract["examples"])


def test_generate_422_error_schema_raises_when_contract_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "azure_functions_validation.openapi.get_validation_error_contract",
        lambda *_args, **_kwargs: None,
    )

    with pytest.raises(ValueError, match="request_model is required"):
        generate_422_error_schema(ExampleRequest)


def test_get_validation_error_examples_raises_when_contract_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "azure_functions_validation.openapi.get_validation_error_contract",
        lambda *_args, **_kwargs: None,
    )

    with pytest.raises(ValueError, match="request_model is required"):
        get_validation_error_examples(ExampleRequest)


class ExampleResponse(BaseModel):
    message: str
    status: str = "ok"


class QueryModel(BaseModel):
    page: int = Field(ge=1)


# --- get_openapi_response_metadata tests ---


def test_get_openapi_response_metadata_with_body_and_response() -> None:
    responses = get_openapi_response_metadata(
        body=ExampleRequest,
        response_model=ExampleResponse,
    )

    assert "200" in responses
    assert "422" in responses

    # 200 has response schema
    assert responses["200"]["description"] == "Successful Response"
    assert "application/json" in responses["200"]["content"]
    schema_200 = responses["200"]["content"]["application/json"]["schema"]
    assert "properties" in schema_200
    assert "message" in schema_200["properties"]

    # 422 has error schema and examples
    assert responses["422"]["description"] == "Validation Error"
    content_422 = responses["422"]["content"]["application/json"]
    assert "schema" in content_422
    assert "examples" in content_422


def test_get_openapi_response_metadata_422_examples_use_correct_loc() -> None:
    responses = get_openapi_response_metadata(
        body=ExampleRequest,
        query=QueryModel,
    )

    assert "422" in responses
    examples = responses["422"]["content"]["application/json"]["examples"]
    all_locs = set()
    for example_data in examples.values():
        for error in example_data["value"]["detail"]:
            all_locs.add(error["loc"][0])
    assert "body" in all_locs
    assert "query" in all_locs


def test_get_openapi_response_metadata_query_only() -> None:
    responses = get_openapi_response_metadata(query=QueryModel)

    assert "200" not in responses
    assert "422" in responses
    examples = responses["422"]["content"]["application/json"]["examples"]
    for example_data in examples.values():
        for error in example_data["value"]["detail"]:
            assert error["loc"][0] == "query"


def test_get_openapi_response_metadata_empty_returns_empty_dict() -> None:
    responses = get_openapi_response_metadata()
    assert responses == {}


def test_get_openapi_response_metadata_rejects_body_and_request_model() -> None:
    with pytest.raises(ValueError, match="Cannot use request_model together with body"):
        get_openapi_response_metadata(body=ExampleRequest, request_model=QueryModel)


def test_get_openapi_response_metadata_request_model_alias() -> None:
    responses = get_openapi_response_metadata(request_model=ExampleRequest)

    assert "422" in responses
    examples = responses["422"]["content"]["application/json"]["examples"]
    for example_data in examples.values():
        for error in example_data["value"]["detail"]:
            assert error["loc"][0] == "body"
