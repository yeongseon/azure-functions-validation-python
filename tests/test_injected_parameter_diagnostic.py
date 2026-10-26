from azure.functions import HttpRequest
from pydantic import BaseModel
import pytest

from azure_functions_validation import validate_http


class Input(BaseModel):
    name: str


def test_mismatched_body_model_parameter_fails_during_decoration() -> None:
    with pytest.raises(ValueError, match="payload.*expected.*body"):

        @validate_http(body=Input)
        def handler(req: HttpRequest, payload: Input) -> Input:
            return payload


def test_correctly_named_model_and_independent_bindings_remain_supported() -> None:
    @validate_http(body=Input)
    def handler(req: HttpRequest, body: Input, context: str) -> Input:
        return body

    assert callable(handler)
