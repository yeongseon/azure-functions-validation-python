"""Portable JSON body parsing limits, independent of CPython's C stack guard."""

import json
from typing import Any, Final

from .errors import MalformedRequestError

_MAX_JSON_DEPTH: Final = 512


def parse_json_body(body: str) -> Any:
    depth = 0
    in_string = False
    escaped = False
    for character in body:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
        elif character == '"':
            in_string = True
        elif character in ("[", "{"):
            depth += 1
            if depth > _MAX_JSON_DEPTH:
                raise MalformedRequestError("Invalid JSON")
        elif character in ("]", "}"):
            depth -= 1
    try:
        return json.loads(body)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise MalformedRequestError("Invalid JSON") from exc
