import azure.functions as func
from pydantic import BaseModel

from azure_functions_validation import validate_http


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
