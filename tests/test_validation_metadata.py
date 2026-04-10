from __future__ import annotations

from azure.functions import HttpRequest
from pydantic import BaseModel

from azure_functions_validation import validate_http


class BodyModel(BaseModel):
    name: str


class QueryModel(BaseModel):
    page: int = 1


class PathModel(BaseModel):
    item_id: str


class HeaderModel(BaseModel):
    x_request_id: str


class ResponseModel(BaseModel):
    ok: bool


def test_metadata_discoverable_on_decorated_function() -> None:
    @validate_http(
        body=BodyModel,
        query=QueryModel,
        path=PathModel,
        headers=HeaderModel,
        response_model=ResponseModel,
    )
    def handler(
        req: HttpRequest,
        body: BodyModel,
        query: QueryModel,
        path: PathModel,
        headers: HeaderModel,
    ) -> ResponseModel:
        return ResponseModel(ok=True)

    metadata = getattr(handler, "_azure_functions_metadata", None)
    assert metadata is not None
    assert "validation" in metadata
    validation = metadata["validation"]
    assert validation["body"] is BodyModel
    assert validation["query"] is QueryModel
    assert validation["path"] is PathModel
    assert validation["headers"] is HeaderModel
    assert validation["response_model"] is ResponseModel


def test_metadata_absent_for_non_decorated_function() -> None:
    def plain_handler(req: HttpRequest) -> dict[str, bool]:
        return {"ok": True}

    assert getattr(plain_handler, "_azure_functions_metadata", None) is None
