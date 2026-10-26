"""Portable JSON body parsing limits, independent of CPython's C stack guard."""

import json
from typing import Any, Final

from .errors import MalformedRequestError

_MAX_JSON_DEPTH: Final = 512


def parse_json_body(body: str) -> Any:
    # Nesting depth never exceeds the number of opening brackets, so a body with at most
    # _MAX_JSON_DEPTH of them (counting those inside strings) skips the pure-Python scan.
    if body.count("[") + body.count("{") > _MAX_JSON_DEPTH:
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
    except (ValueError, RecursionError) as exc:
        raise MalformedRequestError("Invalid JSON") from exc
