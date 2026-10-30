from collections.abc import Mapping, Sequence
from http import HTTPStatus
from typing import Any

from azure.functions.http import HttpResponseConverter
import pytest

from azure_functions_validation._response_transport import (
    build_response,
    json_media_type,
    validation_status,
)


@pytest.mark.parametrize("status", [400, 422, 499, HTTPStatus.CONFLICT])
def test_client_status(status: int) -> None:
    assert validation_status(status) == int(status)


@pytest.mark.parametrize("status", [True, False, 399, 500, "400", None, 422.0])
def test_invalid_status(status: Any) -> None:
    with pytest.raises(ValueError):
        validation_status(status)


@pytest.mark.parametrize(
    "media",
    [
        "application/json",
        "APPLICATION/PROBLEM+JSON",
        "application/vnd.a+json",
        "application/vnd.acme+problem+json",
    ],
)
def test_json_media(media: str) -> None:
    assert json_media_type(media) == media.lower()


@pytest.mark.parametrize(
    "media",
    [
        None,
        42,
        "text/json",
        "application/+json",
        "application/*+json",
        "application/json; charset=utf-8",
        " application/json",
        "application/json\n",
    ],
)
def test_invalid_media(media: Any) -> None:
    with pytest.raises(ValueError):
        json_media_type(media)


@pytest.mark.parametrize(
    "headers",
    [
        {"X-Trace": "caf\xe9\tvalue"},
        [("X-Trace", "caf\xe9\tvalue"), ("Content-Type", " APPLICATION/JSON ")],
    ],
)
def test_headers_copy(headers: Mapping[str, str] | Sequence[tuple[str, str]]) -> None:
    response = build_response(b"{}", 201, "application/json", headers)
    assert response.status_code == 201
    assert response.get_body() == b"{}"
    assert response.headers["X-Trace"] == "caf\xe9\tvalue"
    assert response.headers["Content-Type"] == "application/json"


@pytest.mark.parametrize(
    "name",
    [
        "Content-Length",
        "Transfer-Encoding",
        "Connection",
        "Keep-Alive",
        "Proxy-Authenticate",
        "Proxy-Authorization",
        "TE",
        "Trailer",
        "Upgrade",
        "Host",
    ],
)
def test_transport_owned_headers(name: str) -> None:
    with pytest.raises(ValueError):
        build_response("{}", 400, "application/json", {name: "x"})


@pytest.mark.parametrize(
    "headers",
    [
        [("X-A", "one"), ("x-a", "two")],
        [("Content-Type", "application/json"), ("content-type", "application/json")],
        {"Content-Type": "application/problem+json"},
        {"Bad Name": "x"},
        {"": "x"},
        {"caf\xe9": "x"},
        {"X-A": "\r"},
        {"X-A": "\n"},
        {"X-A": "\x00"},
        {"X-A": "\x1f"},
        {"X-A": "\x7f"},
        {"X-A": "\u0100"},
        {"X-A": 4},
        {4: "x"},
        [("a",)],
        "ab",
        [("Set-Cookie", "")],
        [("Set-Cookie", "a=1; b=2")],
        [("Set-Cookie", "a=1, b=2")],
        [("Set-Cookie", "invalid")],
    ],
)
def test_invalid_headers(headers: Any) -> None:
    with pytest.raises((ValueError, UnicodeEncodeError)):
        build_response("{}", 400, "application/json", headers)


def test_cookie_converter_preserves_individual_fields() -> None:
    response = build_response(
        "{}",
        400,
        "application/json",
        [
            ("Set-Cookie", "a=1; Path=/; HttpOnly"),
            ("set-cookie", "b=2; Expires=Wed, 09 Jun 2027 10:18:14 GMT"),
        ],
    )
    encoded = HttpResponseConverter.encode(response, expected_type=None)
    assert encoded is not None
    assert len(encoded.value["cookies"]) == 2
    assert [list(cookie) for cookie in encoded.value["cookies"]] == [["a"], ["b"]]
