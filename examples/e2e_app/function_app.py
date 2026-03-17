"""E2E test function app for azure-functions-validation — uses PydanticAdapter directly."""
from __future__ import annotations

import json

from pydantic import BaseModel, Field
from pydantic import ValidationError as PydanticValidationError
import azure.functions as func
from azure_functions_validation.adapter import PydanticAdapter

app = func.FunctionApp()
adapter = PydanticAdapter()


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
        body = adapter.parse_body(req, CreateItemRequest)
    except PydanticValidationError as exc:
        error = adapter.format_error(exc)
        return func.HttpResponse(json.dumps(error), status_code=422, mimetype="application/json")
    except ValueError as exc:
        return func.HttpResponse(
            json.dumps({"detail": [{"loc": [], "msg": str(exc), "type": "value_error"}]}),
            status_code=422,
            mimetype="application/json",
        )

    response = ItemResponse(id=1, name=body.name, quantity=body.quantity)
    content, content_type = adapter.serialize(response)
    return func.HttpResponse(content, status_code=200, mimetype=content_type)


@app.route(route="items/bad", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def create_item_bad_request(req: func.HttpRequest) -> func.HttpResponse:
    """Intentionally returns 200 when body is valid — e2e tests validate the happy path here."""
    try:
        body = adapter.parse_body(req, CreateItemRequest)
    except PydanticValidationError as exc:
        error = adapter.format_error(exc)
        return func.HttpResponse(json.dumps(error), status_code=422, mimetype="application/json")
    except ValueError as exc:
        return func.HttpResponse(
            json.dumps({"detail": [{"loc": [], "msg": str(exc), "type": "value_error"}]}),
            status_code=422,
            mimetype="application/json",
        )

    return func.HttpResponse(
        json.dumps({"id": 2, "name": body.name, "quantity": body.quantity}),
        mimetype="application/json",
    )
