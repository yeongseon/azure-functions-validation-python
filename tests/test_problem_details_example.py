from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path

from azure.functions import HttpRequest
import pytest


@pytest.mark.parametrize(
    "body,status,media",
    [
        (b"{}", 400, "application/problem+json"),
        (b"broken", 400, "application/json"),
        (b'{"text":"ok"}', 200, "application/json"),
    ],
)
def test_problem_details_example(body: bytes, status: int, media: str) -> None:
    path = Path(__file__).parents[1] / "examples/custom_error_handler/function_app.py"
    spec = spec_from_file_location("problem_example", path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    response = module.create_problem_comment(HttpRequest("POST", "http://localhost", body=body))
    assert response.status_code == status
    assert response.headers["Content-Type"] == media
    content = json.loads(response.get_body())
    if media == "application/problem+json":
        assert content["status"] == 400
        assert content["type"] == "https://example.com/problems/validation"
        assert content["errors"][0]["loc"] == ["body", "text"]
