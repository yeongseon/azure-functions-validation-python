from pydantic import BaseModel
import pytest

from azure_functions_validation import (
    describe_validation_contract,
    get_contract_schema,
    get_request_contract_metadata,
    get_response_contract_metadata,
    get_validation_error_contract,
)


class BodyModel(BaseModel):
    name: str


class QueryModel(BaseModel):
    limit: int


class ResponseModel(BaseModel):
    message: str


def test_get_contract_schema_supports_base_models() -> None:
    schema = get_contract_schema(BodyModel)

    assert schema["type"] == "object"
    assert "name" in schema["properties"]


def test_get_request_contract_metadata_describes_sources() -> None:
    metadata = get_request_contract_metadata(body=BodyModel, query=QueryModel)

    assert set(metadata["sources"]) == {"body", "query"}
    assert metadata["sources"]["body"]["type"] == "BodyModel"
    assert metadata["sources"]["query"]["schema"]["type"] == "object"


def test_get_request_contract_metadata_prefers_request_model_shorthand() -> None:
    metadata = get_request_contract_metadata(request_model=BodyModel)

    assert set(metadata["sources"]) == {"body"}
    assert metadata["sources"]["body"]["type"] == "BodyModel"


def test_get_response_contract_metadata_supports_generic_models() -> None:
    metadata = get_response_contract_metadata(list[ResponseModel])

    assert metadata is not None
    assert metadata["type"] == "list[ResponseModel]"
    assert metadata["schema"]["type"] == "array"
    assert metadata["schema"]["items"]["$ref"] == "#/$defs/ResponseModel"
    assert metadata["schema"]["$defs"]["ResponseModel"]["type"] == "object"


def test_get_validation_error_contract_returns_422_metadata() -> None:
    metadata = get_validation_error_contract(BodyModel)

    assert metadata is not None
    assert metadata["status_code"] == 422
    assert metadata["type"] == "validation_error"
    assert "detail" in metadata["schema"]["properties"]
    assert metadata["examples"]


def test_describe_validation_contract_combines_request_response_and_errors() -> None:
    metadata = describe_validation_contract(
        body=BodyModel,
        query=QueryModel,
        response_model=list[ResponseModel],
    )

    assert set(metadata["request"]["sources"]) == {"body", "query"}
    assert metadata["response"]["schema"]["type"] == "array"
    assert metadata["errors"]["validation"]["status_code"] == 422


def test_get_request_contract_metadata_rejects_body_and_request_model() -> None:
    with pytest.raises(ValueError, match="Cannot use request_model together with body"):
        get_request_contract_metadata(body=QueryModel, request_model=BodyModel)
