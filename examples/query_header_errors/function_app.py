"""Query and header validation errors: a small, offline regression recipe (#629)."""

import azure.functions as func
from pydantic import BaseModel, ConfigDict, Field

from azure_functions_validation import validate_http


class ListQuery(BaseModel):
    limit: int = Field(default=10, ge=1, le=100)


class ApiHeaders(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    x_api_version: str = Field(alias="x-api-version", pattern=r"^v\d+$")


app = func.FunctionApp()


@app.function_name(name="list_items")
@app.route(route="query_header_errors", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(query=ListQuery, headers=ApiHeaders)
def list_items(
    req: func.HttpRequest, query: ListQuery, headers: ApiHeaders
) -> dict[str, int | str]:
    return {"limit": query.limit, "api_version": headers.x_api_version}
