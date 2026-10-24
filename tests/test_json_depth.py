import inspect
import json
import sys

from azure.functions import HttpRequest
from pydantic import BaseModel
import pytest

from azure_functions_validation import validate_http
from azure_functions_validation.testing import MockHttpRequest


class BoundaryModel(BaseModel):
    value: int


@pytest.mark.parametrize("depth", [513, 900, 1000, 1500, 2000, 10000])
@pytest.mark.parametrize("container", ["array", "object"])
def test_parser_recursion_limit_is_a_client_error(depth: int, container: str) -> None:
    # Given valid JSON beyond the portable nesting ceiling, within the byte limit.
    opening, closing = (b"[", b"]") if container == "array" else (b'{"x":', b"}")
    payload = opening * depth + b'"CANARY_SECRET_input"' + closing * depth

    @validate_http(body=BoundaryModel, max_body_bytes=65536)
    def handler(req: HttpRequest) -> None:
        pytest.fail("deep nesting reached handler")

    # When parsed; Then client-controlled depth is malformed input, not a server fault.
    response = handler(MockHttpRequest(body=payload))
    assert response.status_code == 400
    assert json.loads(response.get_body())["detail"] == [
        {"loc": ["body"], "msg": "Invalid JSON", "type": "value_error"}
    ]
    assert "CANARY_SECRET_input" not in response.get_body().decode()


@pytest.mark.parametrize("depth", [1, 40, 511, 512])
def test_json_nesting_at_or_below_ceiling_preserves_model_validation(depth: int) -> None:
    # Given a list contract accepting arbitrary nested JSON values.
    @validate_http(body=list)
    def handler(req: HttpRequest) -> None:
        return None

    # When parsed; Then allowed nesting still reaches the handler.
    response = handler(MockHttpRequest(body=b"[" * depth + b"0" + b"]" * depth))
    assert response.status_code == 204


def test_brackets_in_json_strings_do_not_count_as_nesting() -> None:
    # Given escaped quotes and brackets inside a valid field, not JSON containers.
    @validate_http(body=BoundaryModel)
    def handler(req: HttpRequest) -> None:
        return None

    # When parsed; Then string contents do not trigger depth rejection.
    response = handler(MockHttpRequest(json={"value": 1, "text": '\\"[' * 2000 + "]" * 2000}))
    assert response.status_code == 204


def test_many_sibling_containers_do_not_count_as_nesting() -> None:
    # Given far more than 512 brackets that never nest deeper than two levels.
    @validate_http(body=list)
    def handler(req: HttpRequest) -> None:
        return None

    # When parsed; Then only the nesting depth is limited, not the number of containers.
    response = handler(MockHttpRequest(body=b"[" + b"[0]," * 1000 + b"[0]]"))
    assert response.status_code == 204


def test_nesting_at_the_ceiling_is_accepted_when_strings_add_brackets() -> None:
    # Given exactly 512 nested arrays plus brackets inside a string: 514 brackets in total.
    @validate_http(body=list)
    def handler(req: HttpRequest) -> None:
        return None

    # When parsed; Then the ceiling is inclusive however many brackets the body contains.
    response = handler(MockHttpRequest(body=b"[" * 512 + b'"[{"' + b"]" * 512))
    assert response.status_code == 204


def test_nesting_after_strings_with_every_escape_form_still_counts() -> None:
    # Given strings ending in an escaped backslash and holding an escaped quote, followed by
    # 513 nested arrays.
    strings = json.dumps(["\\", '"', "\\\\"])
    payload = strings[:-1] + "," + "[" * 513 + "0" + "]" * 513 + "]"

    @validate_http(body=list)
    def handler(req: HttpRequest) -> None:
        pytest.fail("deep nesting reached handler")

    # When parsed; Then those strings end where JSON ends them and the nesting is rejected.
    response = handler(MockHttpRequest(body=payload))
    assert response.status_code == 400


def test_parser_stack_exhaustion_below_the_ceiling_is_not_a_server_error() -> None:
    # Given a body within the ceiling and a recursion limit with only 100 frames of headroom.
    @validate_http(body=list)
    def handler(req: HttpRequest) -> None:
        return None

    request = MockHttpRequest(body=b"[" * 400 + b"0" + b"]" * 400)
    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(len(inspect.stack(0)) + 100)
    try:
        # When parsed; Then running out of stack is never a 5xx: CPython 3.11 charges its C
        # parser's recursion to that limit and answers 400, later versions parse the body.
        response = handler(request)
    finally:
        sys.setrecursionlimit(limit)
    assert response.status_code in (204, 400)
