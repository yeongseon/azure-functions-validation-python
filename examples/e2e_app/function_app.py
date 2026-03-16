"""E2E test function app for azure-functions-validation — minimal probe build."""
from __future__ import annotations

import json
import logging

import azure.functions as func

app = func.FunctionApp()

logger = logging.getLogger(__name__)
logger.warning("function_app module loaded OK (minimal build)")


@app.route(route="health", auth_level=func.AuthLevel.ANONYMOUS)
def health(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(json.dumps({"status": "ok"}), mimetype="application/json")
