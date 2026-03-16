"""E2E test function app for azure-functions-validation — pydantic model probe."""
from __future__ import annotations

import json
import logging
import traceback

from pydantic import BaseModel, Field
import azure.functions as func
from azure_functions_validation import validate_http

app = func.FunctionApp()

_IMPORT_ERROR: str | None = None
_MODELS_OK = False

try:
    class CreateItemRequest(BaseModel):
        name: str = Field(min_length=1, max_length=100)
        quantity: int = Field(ge=1)

    class ItemResponse(BaseModel):
        id: int
        name: str
        quantity: int

    _MODELS_OK = True
except Exception:
    _IMPORT_ERROR = traceback.format_exc()

logger = logging.getLogger(__name__)


@app.route(route="health", auth_level=func.AuthLevel.ANONYMOUS)
def health(req: func.HttpRequest) -> func.HttpResponse:
    body = {
        "status": "ok" if _MODELS_OK else "model_error",
        "models_ok": _MODELS_OK,
        "import_error": _IMPORT_ERROR,
    }
    return func.HttpResponse(json.dumps(body), status_code=200, mimetype="application/json")
