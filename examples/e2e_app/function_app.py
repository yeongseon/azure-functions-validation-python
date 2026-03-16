"""E2E test function app for azure-functions-validation."""
from __future__ import annotations

import json
import logging
import traceback

import azure.functions as func

# Capture any import errors so the health endpoint can report them.
_IMPORT_ERROR: str | None = None

try:
    from pydantic import BaseModel, Field
    from azure_functions_validation import validate_http

    class CreateItemRequest(BaseModel):
        name: str = Field(min_length=1, max_length=100)
        quantity: int = Field(ge=1)

    class ItemResponse(BaseModel):
        id: int
        name: str
        quantity: int

    _VALIDATION_AVAILABLE = True

except Exception:
    _IMPORT_ERROR = traceback.format_exc()
    _VALIDATION_AVAILABLE = False

app = func.FunctionApp()

logger = logging.getLogger(__name__)
logger.warning("function_app module loaded, validation_available=%s", _VALIDATION_AVAILABLE)


@app.route(route="health", auth_level=func.AuthLevel.ANONYMOUS)
def health(req: func.HttpRequest) -> func.HttpResponse:
    if _IMPORT_ERROR:
        body = {"status": "error", "import_error": _IMPORT_ERROR}
        # Return 200 so warmup passes and we can read the error from tests.
        return func.HttpResponse(json.dumps(body), status_code=200, mimetype="application/json")
    return func.HttpResponse(json.dumps({"status": "ok"}), mimetype="application/json")


if _VALIDATION_AVAILABLE:

    @app.route(route="items", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
    @validate_http(body=CreateItemRequest, response_model=ItemResponse)  # type: ignore[name-defined]
    def create_item(req: func.HttpRequest, body: CreateItemRequest) -> ItemResponse:  # type: ignore[name-defined]
        logging.info("create_item called: %s", body.name)
        return ItemResponse(id=1, name=body.name, quantity=body.quantity)  # type: ignore[name-defined]

    @app.route(route="items/bad", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
    @validate_http(body=CreateItemRequest)  # type: ignore[name-defined]
    def create_item_bad_request(req: func.HttpRequest, body: CreateItemRequest) -> func.HttpResponse:  # type: ignore[name-defined]
        """Intentionally returns 422 when body is invalid — used by e2e tests."""
        return func.HttpResponse(
            json.dumps({"id": 2, "name": body.name, "quantity": body.quantity}),
            mimetype="application/json",
        )
