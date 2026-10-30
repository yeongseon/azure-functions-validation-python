"""Explicit scalar query declaration and request contracts."""

from collections.abc import Callable
import inspect
from typing import Annotated, Any

import azure.functions as func
from pydantic import AliasChoices, AliasPath, BaseModel, Field, ValidationError
from pydantic.fields import FieldInfo
import pytest

from azure_functions_validation._query_params import build_query_params


def _handler(req: func.HttpRequest, *, page: int) -> None:
    pass


@pytest.mark.parametrize(
    "annotation", [int, int | None], ids=["missing-required", "nullable-required"]
)
def test_missing_without_default_is_required(annotation: Any) -> None:
    model, names = build_query_params(_handler, {"page": annotation}, "req")
    with pytest.raises(ValidationError):
        model.model_validate({})
    assert names == ("page",)


@pytest.mark.parametrize(
    "annotation",
    [dict[str, int], BaseModel, list[list[int]], Any, object, Callable[..., int]],
    ids=["map", "model", "nested-list", "any", "object", "unsupported"],
)
def test_non_flat_declarations_fail_at_decoration(annotation: Any) -> None:
    with pytest.raises(ValueError):
        build_query_params(_handler, {"page": annotation}, "req")


@pytest.mark.parametrize("alias", [AliasChoices("a", "b"), AliasPath("a", "b")])
def test_complex_inbound_alias_rejected(alias: Any) -> None:
    with pytest.raises(ValueError, match="flat string"):
        build_query_params(_handler, {"page": Annotated[int, Field(validation_alias=alias)]}, "req")


@pytest.mark.parametrize(
    "handler",
    [lambda req: None, lambda req, page: None, lambda req, *page: None, lambda req, **page: None],
    ids=["absent", "positional-or-keyword", "variadic-positional", "variadic-keyword"],
)
def test_explicit_keyword_only_parameter_required(handler: Callable[..., Any]) -> None:
    with pytest.raises(ValueError, match="keyword-only"):
        build_query_params(handler, {"page": int}, "req")


def test_positional_only_parameter_rejected() -> None:
    def handler(req: func.HttpRequest, page: int, /) -> None:
        pass

    with pytest.raises(ValueError, match="keyword-only"):
        build_query_params(handler, {"page": int}, "req")


@pytest.mark.parametrize(
    "name", ["req", "context", "http_request", "body", "query", "path", "headers", "req_model"]
)
def test_reserved_name_rejected(name: str) -> None:
    with pytest.raises(ValueError, match="reserved"):
        build_query_params(_handler, {name: int}, "req")


def test_sdk_binding_annotation_rejected() -> None:
    def handler(req: func.HttpRequest, *, page: func.Out[str]) -> None:
        pass

    with pytest.raises(ValueError, match="SDK binding"):
        build_query_params(handler, {"page": int}, "req")


@pytest.mark.parametrize("metadata", [Field(default=1), Field(default_factory=lambda: 1)])
def test_two_default_sources_rejected(metadata: Any) -> None:
    def handler(req: func.HttpRequest, *, page: int = 1) -> None:
        pass

    with pytest.raises(ValueError, match="both places"):
        build_query_params(handler, {"page": Annotated[int, metadata]}, "req")


def test_fieldinfo_handler_default_rejected() -> None:
    def handler(req: func.HttpRequest, *, page: int = Field(default=1)) -> None:
        pass

    with pytest.raises(ValueError, match="Annotated"):
        build_query_params(handler, {"page": int}, "req")


@pytest.mark.parametrize("alias", ["page", "shared"], ids=["cross-field-name", "duplicate-alias"])
def test_ambiguous_alias_rejected(alias: str) -> None:
    def handler(req: func.HttpRequest, *, page: int, size: int) -> None:
        pass

    with pytest.raises(ValueError, match="ambiguous"):
        build_query_params(
            handler,
            {
                "page": Annotated[int, Field(alias="shared")],
                "size": Annotated[int, Field(alias=alias)],
            },
            "req",
        )


def test_unresolved_reference_rejected() -> None:
    with pytest.raises(ValueError, match="resolve"):
        build_query_params(_handler, {"page": "MissingQueryType"}, "req")


def test_resolved_reference_uses_declaration_not_handler_annotation() -> None:
    model, _ = build_query_params(_handler, {"page": "str"}, "req")
    assert getattr(model.model_validate({"page": "two"}), "page") == "two"


def test_handler_default_is_validated() -> None:
    def handler(req: func.HttpRequest, *, page: int = 0) -> None:
        pass

    model, _ = build_query_params(handler, {"page": Annotated[int, Field(ge=1)]}, "req")
    with pytest.raises(ValidationError):
        model.model_validate({})


def test_default_factory_not_called_by_metadata() -> None:
    calls: list[int] = []

    def factory() -> int:
        calls.append(1)
        return len(calls)

    model, _ = build_query_params(
        _handler, {"page": Annotated[int, Field(default_factory=factory)]}, "req"
    )
    assert calls == []
    assert getattr(model.model_validate({}), "page") == 1
    assert getattr(model.model_validate({}), "page") == 2


def test_declaration_metadata_is_copied() -> None:
    field = Field(alias="page-size", default=1)
    assert isinstance(field, FieldInfo)
    declaration = {"page": Annotated[int, field]}
    model, _ = build_query_params(_handler, declaration, "req")
    declaration.clear()
    field.alias = "changed"
    assert getattr(model.model_validate({"page-size": "2"}), "page") == 2
    assert inspect.signature(_handler).parameters["page"].default is inspect.Parameter.empty
