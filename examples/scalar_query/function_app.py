"""Scalar query validation without a ``BaseModel`` (opt-in ``query_params``) (#631)."""

from datetime import date
from enum import StrEnum
from typing import Annotated

import azure.functions as func
from pydantic import Field

from azure_functions_validation import validate_http


class Color(StrEnum):
    RED = "red"
    BLUE = "blue"


app = func.FunctionApp()


@app.function_name(name="search_items")
@app.route(route="scalar_query/search", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(
    query_params={
        "page": Annotated[int, Field(ge=1)],
        "tags": list[str],
        "since": date | None,
        "color": Color,
        "size": Annotated[int, Field(alias="page-size", le=50)],
    }
)
def search_items(
    req: func.HttpRequest,
    *,
    tags: list[str],
    since: date | None = None,
    color: Color = Color.RED,
    page: int = 1,
    size: int = 10,
) -> dict[str, object]:
    return {
        "page": page,
        "tags": tags,
        "since": since.isoformat() if since else None,
        "color": color.value,
        "size": size,
    }


@app.function_name(name="undeclared_query")
@app.route(route="scalar_query/undeclared", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http()
def undeclared_query(req: func.HttpRequest) -> dict[str, str | None]:
    """No ``query_params``: nothing is validated or injected; read ``req.params`` yourself."""
    return {"page": req.params.get("page")}
