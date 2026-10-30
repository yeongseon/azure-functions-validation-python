import azure.functions as func
from pydantic import BaseModel

from azure_functions_validation import (
    AdapterValidationError,
    ValidationErrorResponse,
    validate_http,
)


class CommentRequest(BaseModel):
    text: str


def custom_error_formatter(exc: Exception, status_code: int) -> dict[str, object]:
    message = str(exc) if status_code < 500 else "Internal Server Error"
    return {
        "error": {
            "code": f"VALIDATION_{status_code}",
            "message": message,
        }
    }


app = func.FunctionApp()


@app.function_name(name="create_comment")
@app.route(route="comments", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(body=CommentRequest, error_formatter=custom_error_formatter)
def create_comment(req: func.HttpRequest, body: CommentRequest) -> dict[str, str]:
    return {"text": body.text, "status": "accepted"}


class ProblemDetails(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    errors: list[dict[str, object]] | None = None


def problem_details(exc: Exception, status_code: int) -> dict[str, object]:
    if status_code != 422:
        return {"title": str(exc), "status": status_code}
    return {
        "type": "https://example.com/problems/validation",
        "title": "Invalid request",
        "status": 400,
        "detail": "Correct the invalid request fields and try again.",
        "errors": exc.errors if isinstance(exc, AdapterValidationError) else None,
    }


@app.function_name(name="create_problem_comment")
@app.route(route="problem-comments", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@validate_http(
    body=CommentRequest,
    error_formatter=problem_details,
    validation_error_response=ValidationErrorResponse(
        status_code=400,
        media_type="application/problem+json",
        response_model=ProblemDetails,
    ),
)
def create_problem_comment(req: func.HttpRequest, body: CommentRequest) -> dict[str, str]:
    return {"text": body.text, "status": "accepted"}
