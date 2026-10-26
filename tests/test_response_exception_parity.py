import json
import logging
from unittest.mock import Mock

from azure.functions import HttpRequest
from pydantic import BaseModel
import pytest

from azure_functions_validation import PydanticAdapter, validate_http


class Output(BaseModel):
    value: int


@pytest.mark.parametrize("seam", ["validate_response", "serialize_response", "serialize"])
@pytest.mark.parametrize("error_type", [TypeError, ValueError, RuntimeError])
@pytest.mark.parametrize("expose", [False, True])
def test_response_faults_preserve_formatter_status_and_logging(
    seam: str, error_type: type[Exception], expose: bool, caplog: pytest.LogCaptureFixture
) -> None:
    original = error_type("private-canary")
    adapter = PydanticAdapter()
    setattr(adapter, seam, Mock(side_effect=original))
    captured: list[tuple[Exception, int]] = []

    def formatter(exc: Exception, status: int) -> dict[str, str]:
        captured.append((exc, status))
        return {"error": "safe"}

    @validate_http(
        adapter=adapter,
        response_model=Output if seam != "serialize" else None,
        error_formatter=formatter,
        expose_internal_errors=expose,
    )
    def handler(req: HttpRequest) -> dict[str, int]:
        return {"value": 1}

    with caplog.at_level(logging.ERROR):
        response = handler(HttpRequest("GET", "https://example.test", body=b""))
    assert response.status_code == 500
    assert json.loads(response.get_body()) == {"error": "safe"}
    assert captured[0][1] == 500
    assert (captured[0][0] is original) == expose
    errors = [record for record in caplog.records if record.exc_info]
    assert len(errors) == 1
    assert errors[0].exc_info is not None
    assert errors[0].exc_info[1] is original
