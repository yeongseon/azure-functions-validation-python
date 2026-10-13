from azure_functions_validation._metadata import (
    METADATA_ATTR,
    ValidationMetadata,
    set_validation_metadata,
)


def test_set_validation_metadata_replaces_stale_validation_namespace() -> None:
    def source_handler() -> None:
        pass

    def wrapped_handler() -> None:
        pass

    existing = {
        "openapi": {"operation_id": "createUser"},
        "validation": {"version": 0, "body": "stale"},
    }
    payload = ValidationMetadata(
        version=1,
        body=None,
        query=None,
        path=None,
        headers=None,
        response_model=None,
    )
    setattr(source_handler, METADATA_ATTR, existing)

    set_validation_metadata(wrapped_handler, source_handler, payload)

    assert getattr(wrapped_handler, METADATA_ATTR) == {
        "openapi": {"operation_id": "createUser"},
        "validation": payload,
    }


def test_set_validation_metadata_does_not_mutate_source_mapping() -> None:
    def source_handler() -> None:
        pass

    def wrapped_handler() -> None:
        pass

    existing = {"openapi": {"operation_id": "createUser"}}
    payload = ValidationMetadata(
        version=1,
        body=None,
        query=None,
        path=None,
        headers=None,
        response_model=None,
    )
    setattr(source_handler, METADATA_ATTR, existing)

    set_validation_metadata(wrapped_handler, source_handler, payload)

    assert existing == {"openapi": {"operation_id": "createUser"}}
