from __future__ import annotations

import json
import logging
from unittest.mock import Mock

from azure.functions import HttpRequest
from pydantic import BaseModel, ConfigDict, Field
import pytest

from azure_functions_validation import PydanticAdapter, validate_http
from azure_functions_validation.testing import MockHttpRequest


class BoundaryModel(BaseModel):
    model_config = ConfigDict(strict=True, allow_inf_nan=False)
    value: int
    items: list[int] = Field(default_factory=list, max_length=8)


@pytest.mark.parametrize(
    "payload,status",
    [
        (b'{"value":"CANARY_SECRET_input"}', 422),
        (b'{"value":"CANARY_SECRET_input",}', 400),
        (b"\xffCANARY_SECRET_input", 400),
        (b'{"value":NaN}', 422),
        (b'{"value":Infinity}', 422),
        (b'{"value":-Infinity}', 422),
        (b'{"value":1,"value":"CANARY_SECRET_input"}', 422),
        (b"[" * 40 + b'"CANARY_SECRET_input"' + b"]" * 40, 422),
    ],
)
def test_adversarial_input_returns_sanitized_client_error(
    payload: bytes, status: int, caplog: pytest.LogCaptureFixture
) -> None:
    # Given constrained models and hostile inputs below a deterministic byte limit.
    @validate_http(body=BoundaryModel, max_body_bytes=256, require_json_content_type=True)
    def handler(req: HttpRequest) -> None:
        pytest.fail("invalid input reached the handler")

    # When invoked; Then only normalized error metadata escapes.
    with caplog.at_level(logging.DEBUG):
        response = handler(
            MockHttpRequest(body=payload, headers={"Content-Type": "application/json"})
        )
    assert response.status_code == status
    assert "CANARY_SECRET_input" not in response.get_body().decode() + caplog.text
    assert all(
        set(entry) == {"loc", "msg", "type"} for entry in json.loads(response.get_body())["detail"]
    )


@pytest.mark.parametrize(
    "payload", [b"[" * 2000 + b"]" * 2000, b"[0," * 2000, b'"' + b"x" * 4096 + b'"']
)
def test_oversize_input_is_rejected_before_adapter_or_model_work(payload: bytes) -> None:
    # Given oversized nesting/arrays/strings and a narrow parser call-count spy.
    adapter = PydanticAdapter()
    parse = Mock(wraps=adapter.parse_body)
    setattr(adapter, "parse_body", parse)

    @validate_http(body=BoundaryModel, adapter=adapter, max_body_bytes=64)
    def handler(req: HttpRequest) -> None:
        pytest.fail("oversized input reached the handler")

    # When invoked; Then the pipeline performs no JSON/model parsing.
    response = handler(MockHttpRequest(body=payload))
    assert response.status_code == 413
    parse.assert_not_called()
    assert len(response.get_body()) < 256


def test_mismatched_media_type_is_rejected_before_adapter_work() -> None:
    # Given a JSON-looking body advertised as text and a parser spy.
    adapter = PydanticAdapter()
    parse = Mock(wraps=adapter.parse_body)
    setattr(adapter, "parse_body", parse)

    @validate_http(body=BoundaryModel, adapter=adapter, require_json_content_type=True)
    def handler(req: HttpRequest) -> None:
        pytest.fail("wrong media type reached handler")

    # When invoked; Then content-type policy rejects it without parsing.
    response = handler(MockHttpRequest(body=b'{"value":1}', headers={"Content-Type": "text/plain"}))
    assert response.status_code == 415
    parse.assert_not_called()


def test_nested_expansion_has_no_implicit_error_count_cap() -> None:
    # Given a finite, byte-limited nested request with many invalid array members.
    class Nested(BaseModel):
        values: list[BoundaryModel]

    @validate_http(body=Nested, max_body_bytes=4096)
    def handler(req: HttpRequest) -> None:
        pytest.fail("invalid nesting reached handler")

    # When invoked; Then characterize the existing uncapped contract, not a promised cap.
    response = handler(MockHttpRequest(json={"values": [{"value": "CANARY_SECRET_input"}] * 32}))
    assert response.status_code == 422
    assert len(json.loads(response.get_body())["detail"]) == 32
    assert "CANARY_SECRET_input" not in response.get_body().decode()


def test_parser_recursion_limit_is_a_client_error() -> None:
    # Given valid JSON nesting beyond the interpreter parser's recursion limit.
    @validate_http(body=BoundaryModel, max_body_bytes=8192)
    def handler(req: HttpRequest) -> None:
        pytest.fail("deep nesting reached handler")

    # When parsed; Then client-controlled depth is malformed input, not a server fault.
    response = handler(MockHttpRequest(body=b"[" * 2000 + b"0" + b"]" * 2000))
    assert response.status_code == 400
    assert json.loads(response.get_body())["detail"] == [
        {"loc": ["body"], "msg": "Invalid JSON", "type": "value_error"}
    ]
