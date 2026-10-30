import os
from typing import Annotated

import azure.functions as func
from pydantic import BaseModel, Field

from azure_functions_validation import ErrorResponseSpec, ValidationErrorResponse, validate_http

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


@app.route(route="scalar-sync", trigger_arg_name="request")
@validate_http(query_params={"page": Annotated[int, Field(ge=1)]})
def scalar_sync(request: func.HttpRequest, context: func.Context, *, page: int = 1) -> dict:
    return {"page": page, "function_name": context.function_name}


@app.route(route="scalar-async", trigger_arg_name="request")
@validate_http(query_params={"tags": list[str]})
async def scalar_async(
    request: func.HttpRequest, context: func.Context, *, tags: list[str]
) -> dict:
    return {"tags": tags, "function_name": context.function_name}


def problem_formatter(exc: Exception, status: int) -> ErrorResponseSpec | dict:
    if status != 422:
        return {"title": str(exc)}
    return ErrorResponseSpec(
        content={"title": "Invalid request", "status": 400}, headers={"X-Error-Contract": "fixed"}
    )


@app.route(route="problem", methods=["POST"])
@validate_http(
    body=InputBody,
    error_formatter=problem_formatter,
    validation_error_response=ValidationErrorResponse(
        status_code=400, media_type="application/problem+json"
    ),
)
def problem(req: func.HttpRequest, context: func.Context, body: InputBody) -> dict:
    return {"function_name": context.function_name, "name": body.name}


@app.route(route="invalid-error", methods=["POST"])
@validate_http(
    body=InputBody,
    error_formatter=lambda exc, status: ErrorResponseSpec(
        content={"secret": "formatter secret"}, status_code=500
    ),
)
def invalid_error(req: func.HttpRequest, context: func.Context) -> dict:
    return {"function_name": context.function_name}
