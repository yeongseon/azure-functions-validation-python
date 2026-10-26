import json
import sys

from azure.functions import HttpRequest
import pytest

from azure_functions_validation import validate_http
from azure_functions_validation.testing import MockHttpRequest


@pytest.mark.parametrize("request_type", [HttpRequest, MockHttpRequest])
def test_oversized_integer_returns_sanitized_client_error(request_type: type[HttpRequest]) -> None:
    """Interpreter integer-conversion limits are client input errors, not handler faults."""
    digits = b"9" * (max(sys.get_int_max_str_digits(), 4300) + 1)
    request = request_type(method="POST", url="http://localhost/", body=b"[" + digits + b"]")

    @validate_http(body=list)
    def handler(req: HttpRequest) -> None:
        pytest.fail("oversized integer reached handler")

    response = handler(request)

    assert response.status_code == 400
    assert json.loads(response.get_body()) == {
        "detail": [{"loc": ["body"], "msg": "Invalid JSON", "type": "value_error"}],
        "error_format_version": 1,
    }
    assert digits not in response.get_body()


@pytest.mark.anyio
@pytest.mark.parametrize("request_type", [HttpRequest, MockHttpRequest])
async def test_async_oversized_integer_returns_sanitized_client_error(
    request_type: type[HttpRequest],
) -> None:
    """Async handlers share the same sanitized parser boundary as synchronous handlers."""
    digits = b"9" * (max(sys.get_int_max_str_digits(), 4300) + 1)
    request = request_type(method="POST", url="http://localhost/", body=b"[" + digits + b"]")

    @validate_http(body=list)
    async def handler(req: HttpRequest) -> None:
        pytest.fail("oversized integer reached handler")

    response = await handler(request)

    assert response.status_code == 400
    assert json.loads(response.get_body()) == {
        "detail": [{"loc": ["body"], "msg": "Invalid JSON", "type": "value_error"}],
        "error_format_version": 1,
    }
    assert digits not in response.get_body()
