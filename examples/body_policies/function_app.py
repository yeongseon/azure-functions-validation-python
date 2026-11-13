"""Opt-in JSON content-type and request-size policies, permitted vs refused (#635)."""

import azure.functions as func
from pydantic import BaseModel

from azure_functions_validation import validate_http


class Note(BaseModel):
    text: str


app = func.FunctionApp()


@app.function_name(name="note_relaxed")
@app.route(route="body_policies/relaxed", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(body=Note)
def note_relaxed(req: func.HttpRequest, body: Note) -> dict[str, str]:
    """Default: no size limit, and any Content-Type is parsed as JSON."""
    return {"text": body.text}


@app.function_name(name="note_strict")
@app.route(route="body_policies/strict", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(body=Note, require_json_content_type=True, max_body_bytes=64)
def note_strict(req: func.HttpRequest, body: Note) -> dict[str, str]:
    """Opt-in: ``415`` for a non-JSON media type, ``413`` above 64 bytes."""
    return {"text": body.text}
