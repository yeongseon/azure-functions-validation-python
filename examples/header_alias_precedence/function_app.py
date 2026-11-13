"""Header alias precedence with ``AliasChoices``: the first listed alias wins (#636)."""

import azure.functions as func
from pydantic import AliasChoices, BaseModel, Field

from azure_functions_validation import validate_http


class ApiKeyHeaders(BaseModel):
    # Order matters: "x-api-key" is preferred; "x-legacy-api-key" is the fallback.
    api_key: str = Field(validation_alias=AliasChoices("x-api-key", "x-legacy-api-key"))


app = func.FunctionApp()


@app.function_name(name="whoami")
@app.route(route="header_alias_precedence", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(headers=ApiKeyHeaders)
def whoami(req: func.HttpRequest, headers: ApiKeyHeaders) -> dict[str, str]:
    return {"api_key": headers.api_key}
