"""Serialized Pydantic field aliases in HTTP responses (#673)."""

from __future__ import annotations

import azure.functions as func
from pydantic import BaseModel, Field

from azure_functions_validation import validate_http


class ItemSummaryResponse(BaseModel):
    item_id: int = Field(alias="id")
    title: str
    is_active: bool = Field(default=True, alias="active")


app = func.FunctionApp()


@app.function_name(name="get_item_summary")
@app.route(
    route="response_field_aliases/summary", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS
)
@validate_http(response_model=ItemSummaryResponse)
def get_item_summary(req: func.HttpRequest) -> ItemSummaryResponse:
    """Default: response_by_alias=True emits declared Field aliases on the wire."""
    return ItemSummaryResponse(id=1, title="Widget", active=True)


@app.function_name(name="get_item_summary_by_name")
@app.route(
    route="response_field_aliases/by-name", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS
)
@validate_http(response_model=ItemSummaryResponse, response_by_alias=False)
def get_item_summary_by_name(req: func.HttpRequest) -> ItemSummaryResponse:
    """Explicit response_by_alias=False emits Python field names instead of aliases."""
    return ItemSummaryResponse(id=1, title="Widget", active=True)
