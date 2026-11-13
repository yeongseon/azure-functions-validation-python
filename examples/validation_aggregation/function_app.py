"""Fail-fast vs opt-in aggregation of validation errors across sources (#633)."""

import azure.functions as func
from pydantic import BaseModel, Field

from azure_functions_validation import validate_http


class OrderBody(BaseModel):
    sku: str = Field(min_length=3)


class OrderQuery(BaseModel):
    quantity: int = Field(ge=1)


app = func.FunctionApp()


@app.function_name(name="order_fail_fast")
@app.route(route="aggregation/fail-fast", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(body=OrderBody, query=OrderQuery)
def order_fail_fast(req: func.HttpRequest, body: OrderBody, query: OrderQuery) -> dict[str, object]:
    """Default: the first failing source is the only one reported."""
    return {"sku": body.sku, "quantity": query.quantity}


@app.function_name(name="order_aggregated")
@app.route(route="aggregation/all", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(body=OrderBody, query=OrderQuery, aggregate_validation_errors=True)
def order_aggregated(
    req: func.HttpRequest, body: OrderBody, query: OrderQuery
) -> dict[str, object]:
    """Opt-in: one 422 lists every failing source, in body, query, path, headers order."""
    return {"sku": body.sku, "quantity": query.quantity}
