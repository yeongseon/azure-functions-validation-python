import time

import pytest

from azure_functions_validation._json_body import parse_json_body
from azure_functions_validation.errors import MalformedRequestError


def test_hostile_escaped_quote_string_is_rejected_in_linear_time() -> None:
    # Given a 300 KB unterminated JSON string of escaped quotes and brackets.
    body = '"' + '\\"[' * 100_000
    started = time.perf_counter()
    # When parsing malformed input, then rejection stays well inside a one second bound.
    with pytest.raises(MalformedRequestError):
        parse_json_body(body)
    assert time.perf_counter() - started < 1
