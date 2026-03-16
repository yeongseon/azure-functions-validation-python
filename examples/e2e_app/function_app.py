"""E2E test function app for azure-functions-validation — import probe."""
from __future__ import annotations

import json
import logging
import traceback

import azure.functions as func

app = func.FunctionApp()

_IMPORT_ERROR: str | None = None
_VALIDATION_AVAILABLE = False

try:
    from pydantic import BaseModel, Field
    from azure_functions_validation import validate_http
    _VALIDATION_AVAILABLE = True
except Exception:
    _IMPORT_ERROR = traceback.format_exc()

logger = logging.getLogger(__name__)


@app.route(route="health", auth_level=func.AuthLevel.ANONYMOUS)
def health(req: func.HttpRequest) -> func.HttpResponse:
    body = {
        "status": "ok" if not _IMPORT_ERROR else "import_error",
        "validation_available": _VALIDATION_AVAILABLE,
        "import_error": _IMPORT_ERROR,
    }
    return func.HttpResponse(json.dumps(body), status_code=200, mimetype="application/json")
