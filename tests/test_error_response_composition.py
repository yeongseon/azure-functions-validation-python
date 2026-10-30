from contextvars import ContextVar
from typing import Any

from azure.functions import Context, HttpRequest
from pydantic import BaseModel

from azure_functions_validation import ErrorResponseSpec, validate_http


def test_outer_logging_context_observes_early_error_and_preserves_bindings() -> None:
    correlation: ContextVar[str] = ContextVar("correlation")
    observed = []

    class Input(BaseModel):
        name: str

    def formatter(exc: Exception, status: int) -> ErrorResponseSpec:
        return ErrorResponseSpec(
            content={"trace": correlation.get()},
            status_code=400,
            media_type="application/problem+json",
            headers={"X-Trace": correlation.get()},
        )

    @validate_http(body=Input, error_formatter=formatter)
    def validated(req: HttpRequest, context: Context, body: Input) -> dict[str, str]:
        return {"name": context.function_name, "body": body.name}

    def outer(req: HttpRequest, context: Any) -> Any:
        token = correlation.set("trace-618")
        try:
            response = validated(req, context=context)
            observed.append(
                (
                    correlation.get(),
                    response.status_code,
                    response.headers["Content-Type"],
                    response.headers.get("X-Trace"),
                )
            )
            return response
        finally:
            correlation.reset(token)

    class Binding:
        function_name = "composed"

    response = outer(HttpRequest("POST", "http://localhost", body=b"{}"), Binding())
    assert response.status_code == 400
    assert observed == [("trace-618", 400, "application/problem+json", "trace-618")]
    assert (
        outer(HttpRequest("POST", "http://localhost", body=b'{"name":"ok"}'), Binding()).get_body()
        == b'{"name": "composed", "body": "ok"}'
    )
