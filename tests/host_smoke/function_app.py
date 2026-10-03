import azure.functions as func
from pydantic import BaseModel

from azure_functions_validation import validate_http

app = func.FunctionApp()


class PublicResponse(BaseModel):
    function_name: str


class InternalResponse(PublicResponse):
    secret: str


@app.route(route="smoke", auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(response_model=PublicResponse)
def smoke(req: func.HttpRequest, context: func.Context) -> InternalResponse:
    return InternalResponse(function_name=context.function_name, secret="hidden")
