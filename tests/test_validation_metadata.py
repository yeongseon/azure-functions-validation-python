from __future__ import annotations

from dataclasses import FrozenInstanceError

from azure.functions import HttpRequest
from pydantic import BaseModel
import pytest

from azure_functions_validation import get_validation_metadata, validate_http


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

    metadata = get_validation_metadata(handler)
    assert metadata is not None
    assert metadata.body is BodyModel
    assert metadata.query is QueryModel
    assert metadata.path is PathModel
    assert metadata.headers is HeaderModel
    assert metadata.response_model is ResponseModel


def test_get_validation_metadata_returns_none_for_non_decorated_function() -> None:
    def plain_handler(req: HttpRequest) -> dict[str, bool]:
        return {"ok": True}

    assert get_validation_metadata(plain_handler) is None


def test_validation_metadata_is_frozen() -> None:
    @validate_http(body=BodyModel)
    def handler(req: HttpRequest, body: BodyModel) -> dict[str, bool]:
        return {"ok": True}

    metadata = get_validation_metadata(handler)
    assert metadata is not None

    with pytest.raises(FrozenInstanceError):
        setattr(metadata, "body", QueryModel)
