"""Default vs overridden validation-error status and media type (#632)."""

import azure.functions as func
from pydantic import BaseModel

from azure_functions_validation import (
    AdapterValidationError,
    ValidationErrorResponse,
    validate_http,
)


class Comment(BaseModel):
    text: str


app = func.FunctionApp()


@app.function_name(name="comment_default")
@app.route(route="error_status/default", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(body=Comment)
def comment_default(req: func.HttpRequest, body: Comment) -> dict[str, str]:
    """No override: a schema error is ``422`` with ``application/json``."""
    return {"text": body.text}


@app.function_name(name="comment_status_only")
@app.route(route="error_status/status", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(body=Comment, validation_error_response=ValidationErrorResponse(status_code=400))
def comment_status_only(req: func.HttpRequest, body: Comment) -> dict[str, str]:
    """Status-only override: ``400``, the default body and ``application/json``."""
    return {"text": body.text}


def problem(exc: Exception, status_code: int) -> dict[str, object]:
    """The formatter still receives the ORIGINAL classified status (``422``)."""
    errors = exc.errors if isinstance(exc, AdapterValidationError) else []
    return {"title": "Invalid request", "status": 400, "errors": errors}


@app.function_name(name="comment_problem")
@app.route(route="error_status/problem", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(
    body=Comment,
    error_formatter=problem,
    validation_error_response=ValidationErrorResponse(
        status_code=400, media_type="application/problem+json"
    ),
)
def comment_problem(req: func.HttpRequest, body: Comment) -> dict[str, str]:
    """Status and media-type override with a formatter-owned body."""
    return {"text": body.text}
