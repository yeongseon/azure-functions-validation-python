from pydantic import BaseModel, Field

from azure_functions_validation.metadata import get_validation_error_contract
from azure_functions_validation.openapi import (
    generate_422_error_schema,
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
