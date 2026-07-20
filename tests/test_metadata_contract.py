"""Tests for the typed cross-package metadata contract (``_metadata``)."""

from __future__ import annotations

from azure_functions_validation._metadata import (
    METADATA_ATTR,
    NAMESPACE,
    VALIDATION_METADATA_VERSION,
    ValidationMetadata,
    read_validation_metadata,
    set_validation_metadata,
)


def _payload() -> ValidationMetadata:
    return {
        "version": 1,
        "body": None,
        "query": None,
        "path": None,
        "headers": None,
        "response_model": None,
    }


class TestContractConstants:
    def test_attr_name_is_toolkit_convention(self) -> None:
        assert METADATA_ATTR == "_azure_functions_metadata"

    def test_namespace_is_validation(self) -> None:
        assert NAMESPACE == "validation"

    def test_version_constant(self) -> None:
        assert VALIDATION_METADATA_VERSION == 1


class TestSetValidationMetadata:
    def test_writes_payload_onto_wrapper(self) -> None:
        def func() -> None:
            pass

        def wrapper() -> None:
            pass

        set_validation_metadata(wrapper, func, _payload())

        meta = getattr(wrapper, METADATA_ATTR)
        assert meta == {"validation": _payload()}

    def test_seeds_from_existing_namespaces_on_func(self) -> None:
        def func() -> None:
            pass

        def wrapper() -> None:
            pass

        setattr(func, METADATA_ATTR, {"db": {"version": 1, "bindings": []}})
        set_validation_metadata(wrapper, func, _payload())

        meta = getattr(wrapper, METADATA_ATTR)
        assert meta["db"] == {"version": 1, "bindings": []}
        assert meta["validation"] == _payload()

    def test_ignores_non_dict_existing_attr(self) -> None:
        def func() -> None:
            pass

        def wrapper() -> None:
            pass

        setattr(func, METADATA_ATTR, "not-a-dict")
        set_validation_metadata(wrapper, func, _payload())

        meta = getattr(wrapper, METADATA_ATTR)
        assert meta == {"validation": _payload()}


class TestReadValidationMetadata:
    def test_returns_payload_when_present(self) -> None:
        def func() -> None:
            pass

        setattr(func, METADATA_ATTR, {"validation": _payload()})
        assert read_validation_metadata(func) == _payload()

    def test_returns_none_when_attr_missing(self) -> None:
        def func() -> None:
            pass

        assert read_validation_metadata(func) is None

    def test_returns_none_when_attr_not_dict(self) -> None:
        def func() -> None:
            pass

        setattr(func, METADATA_ATTR, "not-a-dict")
        assert read_validation_metadata(func) is None

    def test_returns_none_when_namespace_absent(self) -> None:
        def func() -> None:
            pass

        setattr(func, METADATA_ATTR, {"db": {"version": 1}})
        assert read_validation_metadata(func) is None

    def test_returns_none_when_namespace_not_dict(self) -> None:
        def func() -> None:
            pass

        setattr(func, METADATA_ATTR, {"validation": "not-a-dict"})
        assert read_validation_metadata(func) is None
