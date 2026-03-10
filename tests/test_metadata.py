from pydantic import BaseModel, Field
import pytest
from abc import ABC
from azure.functions import HttpResponse

from azure_functions_validation import (
    describe_validation_contract,
    get_contract_schema,
    get_request_contract_metadata,
    get_response_contract_metadata,
    get_validation_error_contract,
)
from azure_functions_validation.registry import GlobalErrorHandlerRegistry


class BodyModel(BaseModel):
    name: str


class QueryModel(BaseModel):
    limit: int


class ResponseModel(BaseModel):
    message: str


class PathModel(BaseModel):
    item_id: int = Field(ge=1)


class HeaderModel(BaseModel):
    x_api_key: str = Field(min_length=8)


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


# --- loc source tests ---


def test_validation_error_contract_uses_body_loc_by_default() -> None:
    metadata = get_validation_error_contract(BodyModel)
    assert metadata is not None
    for example in metadata["examples"]:
        for error in example["value"]["detail"]:
            assert error["loc"][0] == "body"


def test_validation_error_contract_uses_query_loc() -> None:
    metadata = get_validation_error_contract(query=QueryModel)
    assert metadata is not None
    for example in metadata["examples"]:
        for error in example["value"]["detail"]:
            assert error["loc"][0] == "query"


def test_validation_error_contract_uses_path_loc() -> None:
    metadata = get_validation_error_contract(path=PathModel)
    assert metadata is not None
    for example in metadata["examples"]:
        for error in example["value"]["detail"]:
            assert error["loc"][0] == "path"


def test_validation_error_contract_uses_headers_loc() -> None:
    metadata = get_validation_error_contract(headers=HeaderModel)
    assert metadata is not None
    for example in metadata["examples"]:
        for error in example["value"]["detail"]:
            assert error["loc"][0] == "headers"


def test_validation_error_contract_combines_multiple_sources() -> None:
    metadata = get_validation_error_contract(BodyModel, query=QueryModel, path=PathModel)
    assert metadata is not None
    locs = {
        error["loc"][0] for example in metadata["examples"] for error in example["value"]["detail"]
    }
    assert locs == {"body", "query", "path"}


def test_validation_error_contract_returns_none_when_no_sources() -> None:
    assert get_validation_error_contract(None) is None
    assert get_validation_error_contract() is None


def test_validation_error_contract_rejects_body_and_request_model() -> None:
    with pytest.raises(ValueError, match="Cannot use request_model together with body"):
        get_validation_error_contract(BodyModel, body=QueryModel)


# --- loc schema int support ---


def test_422_error_schema_loc_supports_int_items() -> None:
    metadata = get_validation_error_contract(BodyModel)
    assert metadata is not None
    loc_items = metadata["schema"]["properties"]["detail"]["items"]["properties"]["loc"]["items"]
    assert "oneOf" in loc_items
    types = {item["type"] for item in loc_items["oneOf"]}
    assert types == {"string", "integer"}


# --- describe_validation_contract passes all sources ---


def test_describe_validation_contract_passes_query_to_error_contract() -> None:
    metadata = describe_validation_contract(query=QueryModel)
    error_contract = metadata["errors"]["validation"]
    assert error_contract is not None
    locs = {
        error["loc"][0]
        for example in error_contract["examples"]
        for error in example["value"]["detail"]
    }
    assert "query" in locs


def test_describe_validation_contract_multi_source_errors() -> None:
    metadata = describe_validation_contract(
        body=BodyModel,
        query=QueryModel,
        path=PathModel,
        response_model=ResponseModel,
    )
    error_contract = metadata["errors"]["validation"]
    assert error_contract is not None
    locs = {
        error["loc"][0]
        for example in error_contract["examples"]
        for error in example["value"]["detail"]
    }
    assert locs == {"body", "query", "path"}


def test_global_registry_virtual_subclass_specificity_fallback() -> None:
    class VirtualBaseError(ABC):
        pass

    class RuntimeMarkerError(RuntimeError):
        pass

    VirtualBaseError.register(RuntimeMarkerError)
    GlobalErrorHandlerRegistry.clear()

    def generic_handler(exc: Exception) -> HttpResponse:
        return HttpResponse("generic")

    def virtual_handler(exc: Exception) -> HttpResponse:
        return HttpResponse("virtual")

    GlobalErrorHandlerRegistry.register(Exception, generic_handler)
    GlobalErrorHandlerRegistry.register(VirtualBaseError, virtual_handler)

    selected = GlobalErrorHandlerRegistry.get_handler(RuntimeMarkerError("boom"))

    assert selected is generic_handler
    GlobalErrorHandlerRegistry.clear()


def test_global_registry_prefers_more_specific_handler() -> None:
    GlobalErrorHandlerRegistry.clear()

    def generic_handler(exc: Exception) -> HttpResponse:
        return HttpResponse("generic")

    def specific_handler(exc: Exception) -> HttpResponse:
        return HttpResponse("specific")

    GlobalErrorHandlerRegistry.register(Exception, generic_handler)
    GlobalErrorHandlerRegistry.register(ValueError, specific_handler)

    selected = GlobalErrorHandlerRegistry.get_handler(ValueError("bad"))

    assert selected is specific_handler
    GlobalErrorHandlerRegistry.clear()
