import os

import azure.functions as func
from pydantic import BaseModel

from azure_functions_validation import validate_http

app = func.FunctionApp()


class PublicResponse(BaseModel):
    function_name: str


class InternalResponse(PublicResponse):
    secret: str


class InputBody(BaseModel):
    name: str


if os.environ.get("BROKEN_VALIDATION_WRAPPER") == "1":

    def validate_http(**options):
        return lambda handler: handler


@app.route(route="smoke", auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(response_model=PublicResponse)
def smoke(req: func.HttpRequest, context: func.Context) -> InternalResponse:
    return InternalResponse(function_name=context.function_name, secret="hidden")


@app.route(route="validated", methods=["POST"], trigger_arg_name="request")
@validate_http(body=InputBody, response_model=PublicResponse)
def validated(request: func.HttpRequest, body: InputBody) -> InternalResponse:
    return InternalResponse(function_name=body.name, secret="hidden")


@app.route(route="invalid-response")
@validate_http(response_model=PublicResponse)
def invalid_response(req: func.HttpRequest) -> dict:
    return {"unexpected": "must not leak"}
