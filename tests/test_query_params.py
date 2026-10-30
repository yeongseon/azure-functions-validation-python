"""Explicit scalar query declaration and request contracts."""

from collections.abc import Callable
from datetime import date
from enum import StrEnum
import inspect
import json
from typing import Annotated, Any
from urllib.parse import parse_qsl
from uuid import UUID

import azure.functions as func
from pydantic import AliasChoices, AliasPath, BaseModel, Field, PlainSerializer, ValidationError
from pydantic.fields import FieldInfo
import pytest

from azure_functions_validation import PydanticAdapter, validate_http
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


class _CustomOut(func.Out[str]):
    """A user-defined binding type; the SDK base class decides what it is."""


def test_sdk_binding_subclass_rejected() -> None:
    def handler(req: func.HttpRequest, *, page: _CustomOut) -> None:
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


def test_empty_inbound_alias_rejected() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        build_query_params(_handler, {"page": Annotated[int, Field(alias="")]}, "req")


def test_empty_validation_alias_does_not_fall_back_to_another_name() -> None:
    declaration = Annotated[int, Field(validation_alias="", alias="page")]
    with pytest.raises(ValueError, match="non-empty"):
        build_query_params(_handler, {"page": declaration}, "req")


def test_duplicate_empty_aliases_rejected() -> None:
    def handler(req: func.HttpRequest, *, a: int, b: int) -> None:
        pass

    declarations = {name: Annotated[int, Field(alias="")] for name in ("a", "b")}
    with pytest.raises(ValueError, match="non-empty|ambiguous"):
        build_query_params(handler, declarations, "req")


def test_list_field_fallback_alias_must_not_shadow_another_parameter() -> None:
    def handler(req: func.HttpRequest, *, tags: list[str], page: int) -> None:
        pass

    # Only ``tag`` reads the list, but the parser also wraps the inactive alias ``page``.
    declarations = {
        "tags": Annotated[list[str], Field(alias="page", validation_alias="tag")],
        "page": int,
    }
    with pytest.raises(ValueError, match="ambiguous"):
        build_query_params(handler, declarations, "req")


def test_list_field_with_its_own_alias_coexists_with_a_scalar() -> None:
    @validate_http(
        query_params={
            "tags": Annotated[list[str], Field(alias="t")],
            "page": Annotated[int, Field()],
        }
    )
    def handler(req: func.HttpRequest, *, tags: list[str], page: int) -> dict[str, Any]:
        return {"tags": tags, "page": page}

    response = handler(
        func.HttpRequest(method="GET", url="/api/x?page=2&t=a&t=b", body=b"", params={"page": "2"})
    )
    assert json.loads(response.get_body()) == {"tags": ["a", "b"], "page": 2}


def test_unresolved_reference_rejected() -> None:
    with pytest.raises(ValueError, match="resolve"):
        build_query_params(_handler, {"page": "MissingQueryType"}, "req")


def test_resolved_reference_uses_declaration_not_handler_annotation() -> None:
    model, _ = build_query_params(_handler, {"page": "str"}, "req")
    assert getattr(model.model_validate({"page": "two"}), "page") == "two"


def test_default_validation_cannot_be_disabled_by_the_declaration() -> None:
    def handler(req: func.HttpRequest, *, page: int = 1) -> None:
        pass

    declaration = Annotated[int, Field(ge=5, validate_default=False)]
    model, _ = build_query_params(handler, {"page": declaration}, "req")
    with pytest.raises(ValidationError):
        model.model_validate({})


def test_handler_default_applies_to_an_aliased_constrained_declaration() -> None:
    def handler(req: func.HttpRequest, *, page: int = 1) -> None:
        pass

    declaration = Annotated[int, Field(ge=1, validation_alias="page-size")]
    model, _ = build_query_params(handler, {"page": declaration}, "req")
    assert not model.model_fields["page"].is_required()
    assert getattr(model.model_validate({}), "page") == 1
    assert getattr(model.model_validate({"page-size": 7}), "page") == 7


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


def _request(query: str = "", **options: Any) -> func.HttpRequest:
    return func.HttpRequest(
        method="GET",
        url=f"http://localhost/?{query}",
        params=dict(parse_qsl(query, keep_blank_values=True)),
        body=options.pop("body", b""),
        **options,
    )


@pytest.mark.parametrize(
    ("annotation", "query", "status", "expected"),
    [
        (int, "", 422, None),
        (int | None, "", 422, None),
        (int, "page=2", 200, 2),
        (Annotated[int, Field(ge=1)], "page=0", 422, None),
        (int, "page=", 422, None),
        (str, "page=", 200, ""),
        (int | None, "page=null", 422, None),
        (list[str], "page=a", 200, ["a"]),
        (list[str], "page=a&page=b", 200, ["a", "b"]),
        (int, "page=1&page=2", 422, None),
        (int | list[int], "page=2", 200, 2),
        (int | list[int], "page=2&page=3", 200, [2, 3]),
        (Annotated[int, Field(alias="page-size")], "page-size=2", 200, 2),
        (Annotated[int, Field(validation_alias="page-size")], "page-size=2", 200, 2),
        (Annotated[int, Field(serialization_alias="page-size")], "page=2", 200, 2),
        (Annotated[int, Field(alias="page-size")], "page=2", 422, None),
        (int, "page=2&extra=ignored", 200, 2),
    ],
    ids=[
        "missing-required-http",
        "nullable-required-http",
        "integer-injection",
        "constraint",
        "blank-integer",
        "blank-string",
        "textual-null",
        "singleton-list",
        "repeated-list",
        "repeated-scalar",
        "scalar-or-list-single",
        "scalar-or-list-repeated",
        "alias",
        "validation-alias",
        "serialization-alias-only",
        "alias-disables-name",
        "unknown-key",
    ],
)
def test_query_behavior_table(annotation: Any, query: str, status: int, expected: Any) -> None:
    @validate_http(query_params={"page": annotation})
    def handler(req: func.HttpRequest, *, page: Any) -> dict[str, Any]:
        return {"value": page}

    response = handler(_request(query))
    assert response.status_code == status
    payload = json.loads(response.get_body())
    if status == 200:
        assert payload == {"value": expected}
    else:
        wire_name = "page-size" if "alias" in str(annotation) else "page"
        assert payload["detail"][0]["loc"] == ["query", wire_name]


@pytest.mark.parametrize("declarations", [None, {}], ids=["no-declaration", "empty-mapping"])
def test_empty_declaration_preserves_worker_signature(declarations: Any) -> None:
    wrapped = validate_http(query_params=declarations)(_handler)
    assert set(inspect.signature(wrapped).parameters) == {"req", "page"}


def test_query_model_and_nonempty_shorthand_are_exclusive() -> None:
    with pytest.raises(ValueError, match="mutually exclusive"):
        validate_http(query=BaseModel, query_params={"page": int})


def test_empty_shorthand_leaves_query_model_unchanged() -> None:
    class Query(BaseModel):
        page: int

    @validate_http(query=Query, query_params={})
    def handler(req: func.HttpRequest, query: Query) -> dict[str, int]:
        return {"page": query.page}

    assert json.loads(handler(_request("page=3")).get_body()) == {"page": 3}


class _CustomAdapter(PydanticAdapter):
    pass


@pytest.mark.parametrize(
    "adapter", [_CustomAdapter(), object()], ids=["subclass", "foreign-adapter"]
)
def test_custom_adapter_rejected_for_shorthand(adapter: Any) -> None:
    with pytest.raises(TypeError, match="exact PydanticAdapter"):
        validate_http(query_params={"page": int}, adapter=adapter)


def test_exact_adapter_supported_and_request_value_wins() -> None:
    @validate_http(query_params={"page": int}, adapter=PydanticAdapter())
    def handler(req: func.HttpRequest, *, page: int) -> dict[str, int]:
        return {"page": page}

    assert json.loads(handler(_request("page=2"), page=99).get_body()) == {"page": 2}


@pytest.mark.parametrize(
    "default", ["3", "invalid"], ids=["validated-handler-default", "invalid-default"]
)
def test_http_handler_defaults(default: Any) -> None:
    @validate_http(query_params={"page": int})
    def handler(req: func.HttpRequest, *, page: Any = default) -> dict[str, Any]:
        return {"page": page}

    response = handler(_request())
    assert response.status_code == (200 if default == "3" else 422)
    if default == "3":
        assert json.loads(response.get_body()) == {"page": 3}
    else:
        assert json.loads(response.get_body())["detail"][0]["loc"] == ["query", "page"]


def test_annotated_default_used_without_handler_default() -> None:
    @validate_http(query_params={"page": Annotated[int, Field(default="4")]})
    def handler(req: func.HttpRequest, *, page: int) -> dict[str, int]:
        return {"page": page}

    assert json.loads(handler(_request()).get_body()) == {"page": 4}


def test_factory_runs_per_request_and_model_is_built_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def factory() -> int:
        calls.append(1)
        return len(calls)

    @validate_http(query_params={"page": Annotated[int, Field(default_factory=factory)]})
    def handler(req: func.HttpRequest, *, page: int) -> dict[str, int]:
        return {"page": page}

    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("model creation must not occur per request")

    monkeypatch.setattr("azure_functions_validation._query_params.create_model", forbidden)
    assert calls == []
    assert json.loads(handler(_request()).get_body()) == {"page": 1}
    assert json.loads(handler(_request()).get_body()) == {"page": 2}


class _Choice(StrEnum):
    FIRST = "first"


def test_python_typed_values_reach_handler_without_serialization() -> None:
    @validate_http(
        query_params={
            "day": Annotated[date, PlainSerializer(lambda value: "serialized")],
            "identifier": UUID,
            "choice": _Choice,
        }
    )
    def handler(
        req: func.HttpRequest, *, day: date, identifier: UUID, choice: _Choice
    ) -> dict[str, bool]:
        return {
            "typed": isinstance(day, date)
            and isinstance(identifier, UUID)
            and choice is _Choice.FIRST
        }

    response = handler(
        _request("day=2026-10-30&identifier=12345678-1234-5678-1234-567812345678&choice=first")
    )
    assert json.loads(response.get_body()) == {"typed": True}


@pytest.mark.anyio
async def test_async_handler_uses_same_injection_path() -> None:
    @validate_http(query_params={"page": int})
    async def handler(req: func.HttpRequest, *, page: int) -> dict[str, int]:
        return {"page": page}

    response = await handler(_request("page=2"))
    assert json.loads(response.get_body()) == {"page": 2}


@pytest.mark.parametrize("aggregate", [False, True], ids=["fail-fast", "aggregation"])
def test_source_order_with_other_models(aggregate: bool) -> None:
    class Input(BaseModel):
        value: int

    @validate_http(
        body=Input,
        query_params={"page": int},
        path=Input,
        headers=Input,
        aggregate_validation_errors=aggregate,
    )
    def handler(req: func.HttpRequest, *, page: int) -> None:
        pytest.fail("invalid inputs must not invoke handler")

    response = handler(_request("page=bad", body=b"{}", route_params={}, headers={}))
    assert response.status_code == 422
    locations = [entry["loc"] for entry in json.loads(response.get_body())["detail"]]
    assert locations == (
        [["body", "value"], ["query", "page"], ["path", "value"], ["headers", "value"]]
        if aggregate
        else [["body", "value"]]
    )


def test_mapping_is_copied_when_decorator_created() -> None:
    declarations = {"page": int}
    decorate = validate_http(query_params=declarations)
    declarations.clear()
    handler = decorate(_handler)
    assert handler(_request()).status_code == 422


def test_invalid_mapping_type_rejected() -> None:
    invalid: Any = 3
    with pytest.raises(TypeError, match="mapping"):
        validate_http(query_params=invalid)


@pytest.mark.parametrize(
    "name", ["_private", "model_dump"], ids=["private-name", "model-attribute"]
)
def test_unrepresentable_field_name_rejected(name: str) -> None:
    def handler(req: func.HttpRequest) -> None:
        pass

    setattr(
        handler,
        "__signature__",
        inspect.Signature(
            [
                inspect.Parameter("req", inspect.Parameter.POSITIONAL_OR_KEYWORD),
                inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY),
            ]
        ),
    )
    with pytest.raises(ValueError, match="field name"):
        build_query_params(handler, {name: int}, "req")


def test_unannotated_declared_parameter_supported() -> None:
    def handler(req: func.HttpRequest, *, page: Any) -> dict[str, Any]:
        return {"page": page}

    handler.__annotations__.pop("page")
    wrapped = validate_http(query_params={"page": int})(handler)
    assert json.loads(wrapped(_request("page=2")).get_body()) == {"page": 2}
