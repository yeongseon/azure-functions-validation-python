"""Shared transport checks for explicitly configured response values.

Accepts already serialized bodies; serialization and validation belong to callers.
"""

from collections.abc import Mapping, Sequence
from http.cookies import SimpleCookie
import re

from azure.functions import HttpResponse

_TOKEN = re.compile(r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+", re.ASCII)
_JSON_MEDIA = re.compile(r"application/(?:json|[!#$%&'*+\-.^_`|~0-9a-z]+\+json)", re.ASCII)
_PROHIBITED = frozenset(
    {
        "content-length",
        "transfer-encoding",
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "upgrade",
        "host",
    }
)


def validation_status(status_code: int) -> int:
    """Require a client-error integer, including HTTPStatus but excluding bool."""
    if isinstance(status_code, bool) or not isinstance(status_code, int):
        raise ValueError("validation error status must be an integer from 400 to 499")
    if not 400 <= status_code <= 499:
        raise ValueError("validation error status must be an integer from 400 to 499")
    return int(status_code)


def response_status(status_code: int) -> int:
    """Require a final-response integer, including HTTPStatus but excluding bool."""
    if isinstance(status_code, bool) or not isinstance(status_code, int):
        raise ValueError("response status must be an integer from 200 to 599")
    if not 200 <= status_code <= 599:
        raise ValueError("response status must be an integer from 200 to 599")
    return int(status_code)


def json_media_type(media_type: str) -> str:
    """Normalize a bare JSON application media type without accepting parameters."""
    if (
        not isinstance(media_type, str)
        or not media_type.isascii()
        or "*" in media_type
        or not _JSON_MEDIA.fullmatch(media_type.lower())
    ):
        raise ValueError("media_type must be application/json or application/<subtype>+json")
    return media_type.lower()


def build_response(
    body: str | bytes | None,
    status_code: int,
    media_type: str | None,
    headers: Mapping[str, str] | Sequence[tuple[str, str]] | None = None,
) -> HttpResponse:
    """Copy and check headers, preserving separate Set-Cookie fields on the wire."""
    pairs = list(headers.items()) if isinstance(headers, Mapping) else list(headers or ())
    ordinary = {} if media_type is None else {"Content-Type": media_type}
    cookies: list[str] = []
    seen: set[str] = set()
    for pair in pairs:
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValueError("headers must contain name/value pairs")
        name, value = pair
        if not isinstance(name, str) or not _TOKEN.fullmatch(name):
            raise ValueError("header names must be ASCII HTTP tokens")
        if not isinstance(value, str):
            raise ValueError("header values must be strings")
        value.encode("latin-1")
        if any(ord(char) == 127 or (ord(char) < 32 and char != "\t") for char in value):
            raise ValueError("header values must not contain control characters")
        key = name.lower()
        if key in _PROHIBITED:
            raise ValueError("transport-owned header is prohibited")
        if key in seen and key != "set-cookie":
            raise ValueError("duplicate header name")
        seen.add(key)
        if key == "content-type":
            if media_type is None or value.strip().lower() != media_type.lower():
                raise ValueError("Content-Type must agree with the serialized media type")
        elif key == "set-cookie":
            cookie = SimpleCookie()
            cookie.load(value)
            if len(cookie) != 1 or "," in next(iter(cookie.values())).value:
                raise ValueError("each Set-Cookie field must contain exactly one cookie")
            cookies.append(value)
        else:
            ordinary[name] = value
    response = HttpResponse(body=body, status_code=status_code, headers=ordinary)
    for cookie_value in cookies:
        response.headers.add("Set-Cookie", cookie_value)
    return response
