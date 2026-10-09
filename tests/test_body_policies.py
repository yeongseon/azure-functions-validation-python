from collections.abc import Callable
import json
from typing import Any, TypeAlias
from unittest.mock import Mock

from azure.functions import HttpRequest
from pydantic import BaseModel
import pytest

from azure_functions_validation import (
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
    validate_http,
)

RequestFactory: TypeAlias = Callable[..., HttpRequest]


class BodyModel(BaseModel):
    name: str


def _body_handler(**options: Any) -> Any:
    def handler(req: HttpRequest, body: BodyModel) -> dict[str, str]:
        return {"name": body.name}

    return validate_http(body=BodyModel, **options)(handler)


class TestMaxBodyBytes:
    def test_accepts_body_exactly_at_limit(self, mock_request_factory: RequestFactory) -> None:
        payload = b'{"name":"Ada"}'
        response = _body_handler(max_body_bytes=len(payload))(mock_request_factory(body=payload))

        assert response.status_code == 200

    def test_rejects_body_over_limit_with_default_envelope(
        self, mock_request_factory: RequestFactory
    ) -> None:
        payload = b'{"name":"Ada"}'
        response = _body_handler(max_body_bytes=len(payload) - 1)(
            mock_request_factory(body=payload)
        )

        assert response.status_code == 413
        assert json.loads(response.get_body()) == {
            "detail": [
                {
                    "loc": ["body"],
                    "msg": "Request body too large",
                    "type": "payload_too_large",
                }
            ],
            "error_format_version": 1,
        }

    def test_counts_unicode_payload_in_bytes(self, mock_request_factory: RequestFactory) -> None:
        payload = '{"name":"한"}'.encode()
        response = _body_handler(max_body_bytes=len(payload) - 1)(
            mock_request_factory(body=payload)
        )

        assert response.status_code == 413

    def test_default_has_no_body_limit(self, mock_request_factory: RequestFactory) -> None:
        payload = json.dumps({"name": "x" * 10_000}).encode()
        response = _body_handler()(mock_request_factory(body=payload))

        assert response.status_code == 200

    def test_declared_oversize_is_rejected_without_reading_body(self) -> None:
        request = Mock(spec=HttpRequest)
        request.method = "POST"
        request.url = "https://example.test"
        request.headers = {"CONTENT-LENGTH": "101"}

        response = _body_handler(max_body_bytes=100)(request)

        assert response.status_code == 413
        request.get_body.assert_not_called()

    def test_custom_adapter_is_not_called_for_oversize_body(
        self, mock_request_factory: RequestFactory
    ) -> None:
        adapter = Mock()
        adapter.serialize.return_value = ("{}", "application/json")
        handler = _body_handler(max_body_bytes=1, adapter=adapter)

        response = handler(mock_request_factory(body=b"{}"))

        assert response.status_code == 413
        adapter.parse_body.assert_not_called()


class TestJsonContentType:
    @pytest.mark.parametrize(
        "content_type",
        [
            "application/json",
            "application/json; charset=utf-8",
            "APPLICATION/JSON",
            "application/vnd.api+json",
        ],
    )
    def test_accepts_json_media_types(
        self, content_type: str, mock_request_factory: RequestFactory
    ) -> None:
        response = _body_handler(require_json_content_type=True)(
            mock_request_factory(body=b'{"name":"Ada"}', headers={"Content-Type": content_type})
        )

        assert response.status_code == 200

    @pytest.mark.parametrize("headers", [{"Content-Type": "text/plain"}, {}])
    def test_rejects_non_json_or_missing_media_type_for_nonempty_body(
        self, headers: dict[str, str], mock_request_factory: RequestFactory
    ) -> None:
        response = _body_handler(require_json_content_type=True)(
            mock_request_factory(body=b'{"name":"Ada"}', headers=headers)
        )

        assert response.status_code == 415
        assert json.loads(response.get_body()) == {
            "detail": [
                {
                    "loc": ["headers", "content-type"],
                    "msg": "Unsupported media type; expected application/json",
                    "type": "unsupported_media_type",
                }
            ],
            "error_format_version": 1,
        }

    def test_missing_media_type_with_empty_body_keeps_missing_body_response(
        self, mock_request_factory: RequestFactory
    ) -> None:
        response = _body_handler(require_json_content_type=True)(
            mock_request_factory(body=b"", headers={})
        )

        assert response.status_code == 422
        assert json.loads(response.get_body())["detail"][0]["type"] == "missing"

    def test_default_still_parses_json_regardless_of_media_type(
        self, mock_request_factory: RequestFactory
    ) -> None:
        response = _body_handler()(
            mock_request_factory(body=b'{"name":"Ada"}', headers={"Content-Type": "text/plain"})
        )

        assert response.status_code == 200


class TestBodyPolicyFormatters:
    @pytest.mark.parametrize(
        ("options", "expected_type", "expected_status"),
        [
            ({"max_body_bytes": 1}, PayloadTooLargeError, 413),
            ({"require_json_content_type": True}, UnsupportedMediaTypeError, 415),
        ],
    )
    def test_custom_formatter_receives_original_typed_error(
        self,
        options: dict[str, object],
        expected_type: type[Exception],
        expected_status: int,
        mock_request_factory: RequestFactory,
    ) -> None:
        captured: list[Exception] = []

        def formatter(exc: Exception, status_code: int) -> dict[str, int]:
            captured.append(exc)
            return {"status": status_code}

        response = _body_handler(**options, error_formatter=formatter)(
            mock_request_factory(body=b'{"name":"Ada"}', headers={})
        )

        assert response.status_code == expected_status
        assert len(captured) == 1
        assert isinstance(captured[0], expected_type)

    @pytest.mark.anyio
    async def test_async_handler_applies_body_policies(
        self, mock_request_factory: RequestFactory
    ) -> None:
        @validate_http(body=BodyModel, max_body_bytes=1)
        async def handler(req: HttpRequest, body: BodyModel) -> dict[str, str]:
            return {"name": body.name}

        response = await handler(mock_request_factory(body=b"{}"))

        assert response.status_code == 413
