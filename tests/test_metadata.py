from pydantic import BaseModel

from azure_functions_validation._metadata import (
    METADATA_ATTR,
    VALIDATION_METADATA_VERSION,
    ValidationMetadata,
    read_validation_metadata,
    set_validation_metadata,
)


class RequestModel(BaseModel):
    name: str


class ResponseModel(BaseModel):
    message: str


def source_handler() -> None:
    pass


def wrapped_handler() -> None:
    pass


def test_set_validation_metadata_preserves_other_namespaces() -> None:
    payload = ValidationMetadata(
        version=VALIDATION_METADATA_VERSION,
        body=RequestModel,
        query=None,
        path=None,
        headers=None,
        response_model=ResponseModel,
    )
    setattr(source_handler, METADATA_ATTR, {"openapi": {"operation_id": "createUser"}})

    set_validation_metadata(wrapped_handler, source_handler, payload)

    assert getattr(wrapped_handler, METADATA_ATTR) == {
        "openapi": {"operation_id": "createUser"},
        "validation": payload,
    }


def test_read_validation_metadata_returns_exact_attached_payload() -> None:
    payload = ValidationMetadata(
        version=VALIDATION_METADATA_VERSION,
        body=RequestModel,
        query=None,
        path=None,
        headers=None,
        response_model=ResponseModel,
    )
    setattr(wrapped_handler, METADATA_ATTR, {"validation": payload})

    result = read_validation_metadata(wrapped_handler)

    assert result == payload


def test_read_validation_metadata_rejects_non_mapping_namespace() -> None:
    setattr(wrapped_handler, METADATA_ATTR, {"validation": "invalid"})

    result = read_validation_metadata(wrapped_handler)

    assert result is None
