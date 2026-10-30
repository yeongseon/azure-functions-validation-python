from dataclasses import FrozenInstanceError
from http import HTTPStatus
import json
from typing import Any

from azure.functions import HttpRequest, HttpResponse
from azure.functions.http import HttpResponseConverter
from pydantic import BaseModel, Field
import pytest

from azure_functions_validation import ResponseSpec, validate_http


class Public(BaseModel):
    name: str = Field(serialization_alias="displayName")
    optional: str | None = None
    default: int = 7


class Internal(Public):
    secret: str


def request() -> HttpRequest:
    return HttpRequest("GET", "http://localhost", body=b"")


def test_value_is_inert_frozen_slotted_and_keyword_only() -> None:
    spec = ResponseSpec(content="ok", status_code=True)
    assert spec.status_code is True
    assert not hasattr(spec, "__dict__")
    with pytest.raises(FrozenInstanceError):
        setattr(spec, "content", "changed")
    with pytest.raises(TypeError):
        constructor: Any = ResponseSpec
        constructor("positional")


@pytest.mark.parametrize(
    "content", [Internal(name="Ada", optional=None, secret="private"), {"name": "Ada"}]
)
@pytest.mark.parametrize("by_alias", [False, True])
def test_declared_model_filters_subclass_and_applies_options(content: Any, by_alias: bool) -> None:
    # Given a subclass with private fields, the declared model is the disclosure boundary.
    @validate_http(
        response_model=Public,
        response_by_alias=by_alias,
        response_exclude_none=True,
        response_exclude_unset=True,
        status_code=202,
    )
    def handler(req: HttpRequest) -> ResponseSpec[Public]:
        return ResponseSpec(content=content, status_code=201, headers={"Location": "/users/1"})

    # When
    response = handler(request())
    # Then
    assert response.status_code == 201
    assert response.headers["Location"] == "/users/1"
    assert json.loads(response.get_body()) == {"displayName" if by_alias else "name": "Ada"}


def test_list_model_validates_unwrapped_data() -> None:
    @validate_http(response_model=list[Public], response_exclude_none=True)
    def handler(req: HttpRequest) -> ResponseSpec[list[dict[str, str]]]:
        return ResponseSpec(content=[{"name": "Ada", "secret": "hidden"}])

    assert json.loads(handler(request()).get_body()) == [{"displayName": "Ada", "default": 7}]


@pytest.mark.parametrize("content", [{"wrong": "private"}, None])
def test_nonnullable_model_failure_is_sanitized(content: Any) -> None:
    @validate_http(response_model=Public)
    def handler(req: HttpRequest) -> ResponseSpec[Any]:
        return ResponseSpec(content=content, status_code=201, headers={"X-Private": "hidden"})

    response = handler(request())
    assert response.status_code == 500
    assert response.headers.get("X-Private") is None
    assert json.loads(response.get_body())["detail"][0]["msg"] == "Internal Server Error"


@pytest.mark.parametrize("model", [None, Public | None])
@pytest.mark.parametrize("status", [None, 201, 202, 204, 205, 304])
def test_none_overrides_status_and_preserves_headers(model: Any, status: int | None) -> None:
    @validate_http(response_model=model, status_code=202)
    def handler(req: HttpRequest) -> ResponseSpec[None]:
        return ResponseSpec(content=None, status_code=status, headers={"X-Trace": "empty"})

    response = handler(request())
    assert response.status_code == 204
    assert response.get_body() == b""
    assert response.headers.get("Content-Type") is None
    assert response.headers["X-Trace"] == "empty"


@pytest.mark.parametrize("status", [204, 205, 304])
@pytest.mark.parametrize("content", ["", {}, [], False, 0, {"name": "Ada"}])
def test_bodyless_status_rejects_even_falsy_non_none_content(status: int, content: Any) -> None:
    @validate_http()
    def handler(req: HttpRequest) -> ResponseSpec[Any]:
        return ResponseSpec(content=content, status_code=status)

    assert handler(request()).status_code == 500


@pytest.mark.parametrize("status", [True, False, 100, 199, 600, "201", 201.0])
@pytest.mark.parametrize("inherited", [False, True])
@pytest.mark.parametrize("content", [None, "body"])
def test_invalid_explicit_and_inherited_status_fail_closed(
    status: Any, inherited: bool, content: str | None
) -> None:
    @validate_http(status_code=status if inherited else 200)
    def handler(req: HttpRequest) -> ResponseSpec[str | None]:
        return ResponseSpec(content=content, status_code=None if inherited else status)

    assert handler(request()).status_code == 500


@pytest.mark.parametrize("status", [200, HTTPStatus.CREATED, 202, 299, 400, 599])
def test_valid_status_and_inherited_fallback(status: int) -> None:
    @validate_http(status_code=status)
    def handler(req: HttpRequest) -> ResponseSpec[dict[str, bool]]:
        return ResponseSpec(content={"ok": True})

    response = handler(request())
    assert response.status_code == int(status)
    assert json.loads(response.get_body()) == {"ok": True}


@pytest.mark.parametrize("content", [ResponseSpec(content="inner"), HttpResponse("raw")])
def test_nested_responses_are_rejected_without_a_model(content: Any) -> None:
    @validate_http()
    def handler(req: HttpRequest) -> ResponseSpec[Any]:
        return ResponseSpec(content=content)

    assert handler(request()).status_code == 500


@pytest.mark.parametrize(
    "headers",
    [
        [("X-A", "one"), ("x-a", "two")],
        [("Content-Type", "application/json"), ("content-type", "application/json")],
        {"Content-Type": "application/problem+json"},
        {"Content-Length": "2"},
        {"cOnNeCtIoN": "close"},
        {"Host": "elsewhere"},
        {"Bad Name": "x"},
        {"X-A": "a\r\nb"},
        {"X-A": "\x7f"},
        {"X-A": "\u0100"},
        {"X-A": 4},
        [("Set-Cookie", "a=1; b=2")],
        [("Set-Cookie", "a=1, b=2")],
        [("Set-Cookie", "invalid")],
    ],
)
def test_invalid_headers_are_formatted_without_offending_headers(headers: Any) -> None:
    @validate_http()
    def handler(req: HttpRequest) -> ResponseSpec[dict[str, str]]:
        return ResponseSpec(content={}, headers=headers)

    response = handler(request())
    assert response.status_code == 500
    assert list(response.headers.keys()) == ["Content-Type"]


@pytest.mark.parametrize("model", [None, Public | None])
def test_bodyless_content_type_is_rejected(model: Any) -> None:
    @validate_http(response_model=model)
    def handler(req: HttpRequest) -> ResponseSpec[None]:
        return ResponseSpec(content=None, headers={"content-type": "application/json"})

    assert handler(request()).status_code == 500


@pytest.mark.parametrize("pairs", [False, True])
def test_content_type_agreement_retains_one_authoritative_header(pairs: bool) -> None:
    headers = {"content-type": " APPLICATION/JSON ", "X-Trace": "caf\xe9\tvalue"}

    @validate_http()
    def handler(req: HttpRequest) -> ResponseSpec[dict[str, str]]:
        return ResponseSpec(content={}, headers=list(headers.items()) if pairs else headers)

    response = handler(request())
    assert response.status_code == 200
    assert response.headers.get_all("Content-Type") == ["application/json"]
    assert response.headers["X-Trace"] == "caf\xe9\tvalue"


def test_cookie_pairs_survive_sdk_conversion() -> None:
    @validate_http()
    def handler(req: HttpRequest) -> ResponseSpec[dict[str, str]]:
        return ResponseSpec(
            content={},
            headers=[("Set-Cookie", "a=1; HttpOnly"), ("set-cookie", "b=2; Path=/")],
        )

    encoded = HttpResponseConverter.encode(handler(request()), expected_type=None)
    assert encoded is not None
    assert [list(cookie) for cookie in encoded.value["cookies"]] == [["a"], ["b"]]


def test_sdk_response_remains_identity_preserving_bypass() -> None:
    raw = HttpResponse(b"not a model", status_code=202, headers={"X-Raw": "yes"})

    @validate_http(response_model=Public, status_code=201)
    def handler(req: HttpRequest) -> HttpResponse:
        return raw

    assert handler(request()) is raw


def test_legacy_static_bodyless_status_remains_permissive() -> None:
    @validate_http(status_code=205)
    def handler(req: HttpRequest) -> dict[str, bool]:
        return {"legacy": True}

    response = handler(request())
    assert response.status_code == 205
    assert json.loads(response.get_body()) == {"legacy": True}


def test_construction_fault_is_formatted(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import Mock

    import azure_functions_validation.pipeline as pipeline

    monkeypatch.setattr(pipeline, "build_response", Mock(side_effect=RuntimeError("private")))

    @validate_http()
    def handler(req: HttpRequest) -> ResponseSpec[dict[str, str]]:
        return ResponseSpec(content={}, headers={"X-Private": "hidden"})

    response = handler(request())
    assert response.status_code == 500
    assert response.headers.get("X-Private") is None
    assert json.loads(response.get_body())["detail"][0]["msg"] == "Internal Server Error"
