import azure.functions as func
from pydantic import BaseModel

from azure_functions_validation import validate_http
from azure_functions_validation.openapi import (
    generate_422_error_schema,
    get_openapi_response_metadata,
    get_validation_error_examples,
)


class WidgetRequest(BaseModel):
    name: str


class WidgetResponse(BaseModel):
    id: int
    name: str


# Legacy helpers (still work):
OPENAPI_422_SCHEMA = generate_422_error_schema(WidgetRequest)
OPENAPI_422_EXAMPLES = get_validation_error_examples(WidgetRequest)

# New: single-call bridge for @openapi(response=...)
OPENAPI_RESPONSES = get_openapi_response_metadata(
    body=WidgetRequest,
    response_model=WidgetResponse,
)
# OPENAPI_RESPONSES contains:
#   "200" -> {"description": "Successful Response", "content": {"application/json": {"schema": ...}}}
#   "422" -> {"description": "Validation Error", "content": {"application/json": {"schema": ..., "examples": ...}}}

app = func.FunctionApp()


@app.function_name(name="create_widget")
@app.route(route="widgets", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(body=WidgetRequest, response_model=WidgetResponse)
def create_widget(req: func.HttpRequest, body: WidgetRequest) -> WidgetResponse:
    return WidgetResponse(id=1, name=body.name)
