"""Tests for the @validate_http decorator."""
import asyncio
import json

from azure.functions import HttpRequest, HttpResponse
from pydantic import BaseModel
import pytest

from azure_functions_validation.decorator import validate_http


class QueryModel(BaseModel):
    id: int


class BodyModel(BaseModel):
    name: str
    age: int


class ResponseModel(BaseModel):
    message: str


class PathModel(BaseModel):
    user_id: int


class HeaderModel(BaseModel):
    authorization: str


# --- Success Cases ---


def test_decorator_success_sync():
    @validate_http(body=BodyModel, query=QueryModel, response_model=ResponseModel)
    def handler(body: BodyModel, query: QueryModel):
        return {"message": f"Hello {body.name}, id {query.id}"}

    req = HttpRequest(
        method="POST",
        url="/",
        headers={},
        params={"id": "123"},
        route_params={},
        body=json.dumps({"name": "John", "age": 30}).encode(),
    )
    resp = handler(req)

    assert resp.status_code == 200
    assert json.loads(resp.get_body())["message"] == "Hello John, id 123"


@pytest.mark.asyncio
async def test_decorator_success_async():
    @validate_http(body=BodyModel, response_model=ResponseModel)
    async def handler(body: BodyModel):
        await asyncio.sleep(0.01)
        return {"message": f"Hello {body.name}"}

    req = HttpRequest(
        method="POST",
        url="/",
        headers={},
        params={},
        route_params={},
        body=json.dumps({"name": "Jane", "age": 25}).encode(),
    )
    resp = await handler(req)

    assert resp.status_code == 200
    assert json.loads(resp.get_body())["message"] == "Hello Jane"


def test_http_response_bypass():
    @validate_http(response_model=ResponseModel)
    def handler():
        return HttpResponse("custom response", status_code=201)

    req = HttpRequest(method="GET", url="/", headers={}, params={}, route_params={}, body=None)
    resp = handler(req)
    assert resp.status_code == 201
    assert resp.get_body() == b"custom response"


# --- Error Cases ---


def test_body_invalid_json_returns_400():
    @validate_http(body=BodyModel)
    def handler(body: BodyModel):
        pass  # pragma: no cover

    req = HttpRequest(
        method="POST", url="/", headers={}, params={}, route_params={}, body=b"{'bad json"
    )
    resp = handler(req)

    assert resp.status_code == 400
    body = json.loads(resp.get_body())
    assert body["detail"][0]["type"] == "json_invalid"
    assert body["detail"][0]["loc"] == ["body"]


def test_body_validation_error_returns_422():
    @validate_http(body=BodyModel)
    def handler(body: BodyModel):
        pass  # pragma: no cover

    req = HttpRequest(
        method="POST",
        url="/",
        headers={},
        params={},
        route_params={},
        body=json.dumps({"name": "Test"}).encode(),
    )
    resp = handler(req)

    assert resp.status_code == 422
    body = json.loads(resp.get_body())
    assert body["detail"][0]["type"] == "missing"
    assert body["detail"][0]["loc"] == ["body", "age"]


def test_query_validation_error_returns_422():
    @validate_http(query=QueryModel)
    def handler(query: QueryModel):
        pass  # pragma: no cover

    req = HttpRequest(
        method="GET",
        url="/",
        headers={},
        params={"id": "abc"},  # id should be int
        route_params={},
        body=None,
    )
    resp = handler(req)

    assert resp.status_code == 422
    body = json.loads(resp.get_body())
    assert body["detail"][0]["type"] == "int_parsing"
    assert body["detail"][0]["loc"] == ["query", "id"]


def test_response_validation_error_returns_500():
    @validate_http(response_model=ResponseModel)
    def handler():
        return {"wrong_field": "value"}  # Does not match ResponseModel

    req = HttpRequest(method="GET", url="/", headers={}, params={}, route_params={}, body=None)
    resp = handler(req)

    assert resp.status_code == 500
    body = json.loads(resp.get_body())
    assert body["detail"][0]["type"] == "missing"
    assert body["detail"][0]["loc"] == ["response", "message"]


# --- Additional Comprehensive Tests ---


def test_path_validation_error_returns_422():
    @validate_http(path=PathModel)
    def handler(path: PathModel):
        pass  # pragma: no cover

    req = HttpRequest(
        method="GET",
        url="/",
        headers={},
        params={},
        route_params={"user_id": "not_an_int"},  # user_id should be int
        body=None,
    )
    resp = handler(req)

    assert resp.status_code == 422
    body = json.loads(resp.get_body())
    assert body["detail"][0]["type"] == "int_parsing"
    assert body["detail"][0]["loc"] == ["path", "user_id"]


def test_headers_validation_error_returns_422():
    @validate_http(headers=HeaderModel)
    def handler(headers: HeaderModel):
        pass  # pragma: no cover

    req = HttpRequest(
        method="GET",
        url="/",
        headers={},  # Missing 'authorization'
        params={},
        route_params={},
        body=None,
    )
    resp = handler(req)

    assert resp.status_code == 422
    body = json.loads(resp.get_body())
    assert body["detail"][0]["type"] == "missing"
    assert body["detail"][0]["loc"] == ["headers", "authorization"]


def test_handler_with_http_request_and_models():
    @validate_http(body=BodyModel, query=QueryModel)
    def handler(req: HttpRequest, body: BodyModel, query: QueryModel):
        # Handler can access both the raw request and validated models
        assert req.method == "POST"
        return {"message": f"Hello {body.name}, id {query.id}, method {req.method}"}

    req = HttpRequest(
        method="POST",
        url="/",
        headers={},
        params={"id": "456"},
        route_params={},
        body=json.dumps({"name": "Alice", "age": 28}).encode(),
    )
    resp = handler(req)

    assert resp.status_code == 200
    result = json.loads(resp.get_body())
    assert result["message"] == "Hello Alice, id 456, method POST"


def test_path_validation_success():
    @validate_http(path=PathModel)
    def handler(path: PathModel):
        return {"user_id": path.user_id}

    req = HttpRequest(
        method="GET",
        url="/",
        headers={},
        params={},
        route_params={"user_id": "789"},
        body=None,
    )
    resp = handler(req)

    assert resp.status_code == 200
    result = json.loads(resp.get_body())
    assert result["user_id"] == 789


def test_headers_validation_success():
    @validate_http(headers=HeaderModel)
    def handler(headers: HeaderModel):
        return {"auth": headers.authorization}

    req = HttpRequest(
        method="GET",
        url="/",
        headers={"authorization": "Bearer my-token"},
        params={},
        route_params={},
        body=None,
    )
    resp = handler(req)

    assert resp.status_code == 200
    result = json.loads(resp.get_body())
    assert result["auth"] == "Bearer my-token"
