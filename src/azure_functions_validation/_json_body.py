"""Portable JSON body parsing limits, independent of CPython's C stack guard."""

import json
import re
from typing import Any, Final

from .errors import MalformedRequestError

_MAX_JSON_DEPTH: Final = 512
_JSON_TOKENS = re.compile(r'"(?:[^"\\]|\\.)*"|[{}\[\]]')


def parse_json_body(body: str) -> Any:
    depth = 0
    for token in _JSON_TOKENS.finditer(body):
        value = token.group()
        if value in ("[", "{"):
            depth += 1
            if depth > _MAX_JSON_DEPTH:
                raise MalformedRequestError("Invalid JSON")
        elif value in ("]", "}"):
            depth -= 1
    try:
        return json.loads(body)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise MalformedRequestError("Invalid JSON") from exc
