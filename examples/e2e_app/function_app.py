"""E2E test function app for azure-functions-validation."""

from dataclasses import dataclass
import json
import logging
from typing import NoReturn

import azure.functions as func
from pydantic import BaseModel, ConfigDict, Field

from azure_functions_validation import HttpError, validate_http

app = func.FunctionApp()
logging.warning("[DIAG] app created; _function_builders=%s", len(app._function_builders))


class CreateItemRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    quantity: int = Field(ge=1)


class ItemResponse(BaseModel):
    id: int
    name: str
    quantity: int


class PipelineQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    limit: int = Field(default=10, ge=1)


class PipelinePath(BaseModel):
    model_config = ConfigDict(frozen=True)

    item_id: int = Field(ge=1)


class PipelineHeaders(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    trace_id: str = Field(alias="x-trace-id", min_length=1)


class PipelineEcho(BaseModel):
    model_config = ConfigDict(frozen=True)

    item_id: int
    limit: int
    trace_id: str


class PipelineValue(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: int = Field(ge=1)


class PipelineItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    count: int = 1


class PipelineContextResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    function_name: str


@dataclass(frozen=True, slots=True)
class PipelineDataclass:
    name: str
    count: int


class FormatterFailure(RuntimeError):
    pass


def _raise_formatter_failure(exc: Exception, status_code: int) -> NoReturn:
    raise FormatterFailure(f"formatter failed for status {status_code}")


@app.route(route="health", auth_level=func.AuthLevel.ANONYMOUS)
def health(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(json.dumps({"status": "ok"}), mimetype="application/json")


logging.warning("[DIAG] after health; _function_builders=%s", len(app._function_builders))


@app.route(route="items", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(body=CreateItemRequest, response_model=ItemResponse)
def create_item(req: func.HttpRequest, body: CreateItemRequest) -> ItemResponse:
    return ItemResponse(id=1, name=body.name, quantity=body.quantity)


logging.warning(
    "[DIAG] after create_item; _function_builders=%s type=%s",
    len(app._function_builders),
    type(create_item).__name__,
)


@app.route(
    route="pipeline/parameters/{item_id}",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
@validate_http(
    query=PipelineQuery,
    path=PipelinePath,
    headers=PipelineHeaders,
    response_model=PipelineEcho,
)
def pipeline_parameters(
    req: func.HttpRequest,
    query: PipelineQuery,
    path: PipelinePath,
    headers: PipelineHeaders,
) -> PipelineEcho:
    return PipelineEcho(item_id=path.item_id, limit=query.limit, trace_id=headers.trace_id)


@app.route(route="pipeline/async", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(body=PipelineValue, response_model=PipelineValue)
async def pipeline_async(req: func.HttpRequest, body: PipelineValue) -> PipelineValue:
    return PipelineValue(value=body.value * 2)


@app.route(
    route="pipeline/invalid-response",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
@validate_http(response_model=PipelineItem)
def pipeline_invalid_response(req: func.HttpRequest) -> dict[str, str]:
    return {"unexpected": "contract drift"}


@app.route(route="pipeline/dataclass", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http()
def pipeline_dataclass(req: func.HttpRequest) -> PipelineDataclass:
    return PipelineDataclass(name="dataclass", count=2)


@app.route(route="pipeline/empty", methods=["DELETE"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http()
def pipeline_empty(req: func.HttpRequest) -> None:
    return None


@app.route(route="pipeline/list", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(response_model=list[PipelineItem])
def pipeline_list(req: func.HttpRequest) -> list[PipelineItem]:
    return [
        PipelineItem(name="first", count=1),
        PipelineItem(name="second", count=2),
    ]


@app.route(
    route="pipeline/formatter-failure",
    methods=["POST"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
@validate_http(body=PipelineValue, error_formatter=_raise_formatter_failure)
def pipeline_formatter_failure(
    req: func.HttpRequest,
    body: PipelineValue,
) -> PipelineValue:
    return body


@app.route(route="pipeline/created", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(body=PipelineItem, response_model=PipelineItem, status_code=201)
def pipeline_created(req: func.HttpRequest, body: PipelineItem) -> PipelineItem:
    return body


@app.route(route="pipeline/missing", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http()
def pipeline_missing(req: func.HttpRequest) -> NoReturn:
    raise HttpError(404, "Pipeline item not found")


@app.function_name(name="pipeline_context")
@app.route(route="pipeline/context", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(response_model=PipelineContextResponse)
def pipeline_context(
    req: func.HttpRequest,
    context: func.Context,
) -> PipelineContextResponse:
    return PipelineContextResponse(function_name=context.function_name)
