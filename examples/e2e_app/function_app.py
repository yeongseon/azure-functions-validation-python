"""E2E test function app for azure-functions-validation — minimal probe."""
from __future__ import annotations

import json
import logging
import traceback

import azure.functions as func

app = func.FunctionApp()

logger = logging.getLogger(__name__)


@app.route(route="health", auth_level=func.AuthLevel.ANONYMOUS)
def health(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(json.dumps({"status": "ok"}), mimetype="application/json")
