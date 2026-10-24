from collections.abc import Iterator
import time

import pytest

from azure_functions_validation._json_body import parse_json_body
from azure_functions_validation.errors import MalformedRequestError


class CountedBody(str):
    visits = 0

    def __iter__(self) -> Iterator[str]:
        for character in super().__iter__():
            self.visits += 1
            yield character


def test_unterminated_escaped_quotes_are_scanned_once() -> None:
    # Given a 200 KB unterminated JSON string with adversarial escaped quotes.
    body = CountedBody('"' + '\\"' * 100_000)
    started = time.perf_counter()
    # When parsing malformed input, then rejection takes a single linear scan.
    with pytest.raises(MalformedRequestError):
        parse_json_body(body)
    assert time.perf_counter() - started < 1
    assert body.visits == len(body)
