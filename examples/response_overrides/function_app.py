"""Per-return status and header overrides that still go through ``response_model`` (#630)."""

import azure.functions as func
from pydantic import BaseModel

from azure_functions_validation import ResponseSpec, validate_http


class ItemOut(BaseModel):
    id: int
    name: str


class ItemRecord(ItemOut):
    """A storage record with a field that must never reach the client."""

    internal_note: str


app = func.FunctionApp()


@app.function_name(name="create_item")
@app.route(route="response_overrides/items", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(response_model=ItemOut, status_code=202)
def create_item(req: func.HttpRequest) -> ResponseSpec[ItemRecord]:
    """Override the decorator status (202) with 201 and add a ``Location`` header."""
    record = ItemRecord(id=1, name="alpha", internal_note="not for clients")
    return ResponseSpec(content=record, status_code=201, headers={"Location": "/api/items/1"})


@app.function_name(name="accept_item")
@app.route(
    route="response_overrides/accepted", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS
)
@validate_http(response_model=ItemOut, status_code=202)
def accept_item(req: func.HttpRequest) -> ResponseSpec[ItemOut]:
    """Omit ``status_code``: the decorator's 202 is inherited; only a header is added."""
    return ResponseSpec(content=ItemOut(id=2, name="beta"), headers={"X-Example": "accepted"})


@app.function_name(name="broken_item")
@app.route(route="response_overrides/broken", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(response_model=ItemOut)
def broken_item(req: func.HttpRequest) -> ResponseSpec[dict[str, str]]:
    """Wrong content shape: the override does NOT bypass validation, so this is a 500."""
    return ResponseSpec(content={"id": "not-an-int"}, status_code=201)
