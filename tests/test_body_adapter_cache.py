import json
from unittest.mock import patch

from azure.functions import HttpRequest
from pydantic import BaseModel

from azure_functions_validation import PydanticAdapter, validate_http


class Body(BaseModel):
    value: int


def test_static_body_adapter_is_prepared_before_requests() -> None:
    @validate_http(body=Body)
    def handler(req: HttpRequest, body: Body) -> dict[str, int]:
        return {"value": body.value}

    request = HttpRequest("POST", "https://example.test", body=b'{"value":1}')
    with patch(
        "azure_functions_validation.adapter.TypeAdapter", side_effect=AssertionError("rebuilt")
    ):
        assert handler(request).status_code == 200
        assert handler(request).status_code == 200


def test_custom_adapter_parse_signature_and_shared_models_remain_independent() -> None:
    class Custom(PydanticAdapter):
        def parse_body(self, req: HttpRequest, model: type[BaseModel]) -> BaseModel:
            return model.model_validate({"value": 9})

    adapter = Custom()

    @validate_http(body=Body, query=Body, adapter=adapter)
    def handler(req: HttpRequest, body: Body, query: Body) -> dict[str, int]:
        return {"value": body.value + query.value}

    request = HttpRequest("POST", "https://example.test", params={"value": "2"}, body=b"{}")
    assert json.loads(handler(request).get_body()) == {"value": 11}
