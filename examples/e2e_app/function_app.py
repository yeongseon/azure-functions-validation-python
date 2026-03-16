"""E2E test function app for azure-functions-validation — uses @validate_http decorator."""
from __future__ import annotations

import json

from pydantic import BaseModel, Field
import azure.functions as func
from azure_functions_validation import validate_http

app = func.FunctionApp()


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
@validate_http(body=CreateItemRequest, response_model=ItemResponse)
def create_item(req: func.HttpRequest, body: CreateItemRequest) -> ItemResponse:
    return ItemResponse(id=1, name=body.name, quantity=body.quantity)


@app.route(route="items/bad", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(body=CreateItemRequest)
def create_item_bad_request(req: func.HttpRequest, body: CreateItemRequest) -> func.HttpResponse:
    """Intentionally returns 200 when body is valid — e2e tests validate the happy path here."""
    return func.HttpResponse(
        json.dumps({"id": 2, "name": body.name, "quantity": body.quantity}),
        mimetype="application/json",
    )
