"""E2E test function app for azure-functions-validation — direct API (no decorator)."""
from __future__ import annotations

import json
import logging

from pydantic import BaseModel, Field, ValidationError
import azure.functions as func
from azure_functions_validation.adapter import PydanticAdapter

app = func.FunctionApp()
_adapter = PydanticAdapter()

logger = logging.getLogger(__name__)


class CreateItemRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    quantity: int = Field(ge=1)


class ItemResponse(BaseModel):
    id: int
    name: str
    quantity: int


@app.route(route="health", auth_level=func.AuthLevel.ANONYMOUS)
def health(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(json.dumps({"status": "ok"}), mimetype="application/json")


@app.route(route="items", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def create_item(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = _adapter.parse_body(req, CreateItemRequest)
    except (ValidationError, ValueError) as e:
        errors = _adapter.format_error(e)
        return func.HttpResponse(json.dumps(errors), status_code=422, mimetype="application/json")
    result = ItemResponse(id=1, name=body.name, quantity=body.quantity)
    content, content_type = _adapter.serialize(result)
    return func.HttpResponse(content, status_code=200, headers={"Content-Type": content_type})


@app.route(route="items/bad", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def create_item_bad_request(req: func.HttpRequest) -> func.HttpResponse:
    """Intentionally returns 422 when body is invalid — used by e2e tests."""
    try:
        body = _adapter.parse_body(req, CreateItemRequest)
    except (ValidationError, ValueError) as e:
        errors = _adapter.format_error(e)
        return func.HttpResponse(json.dumps(errors), status_code=422, mimetype="application/json")
    return func.HttpResponse(
        json.dumps({"id": 2, "name": body.name, "quantity": body.quantity}),
        mimetype="application/json",
    )
