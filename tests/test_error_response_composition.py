from contextvars import ContextVar
import inspect
import json
from typing import Any

from azure.functions import Context, HttpRequest, HttpResponse, Out
from pydantic import BaseModel
import pytest

from azure_functions_validation import ErrorResponseSpec, ResponseSpec, validate_http


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


class PublicOutput(BaseModel):
    value: int


class NativeOut(Out[str]):
    def __init__(self) -> None:
        self.value = ""

    def set(self, val: str) -> None:
        self.value = val

    def get(self) -> str:
        return self.value


def test_envelope_preserves_worker_signature_bindings_and_foreign_namespaces() -> None:
    def original(req: HttpRequest, output: Out[str]) -> ResponseSpec[PublicOutput]:
        output.set("untouched")
        return ResponseSpec(content=PublicOutput(value=7), status_code=201)

    foreign = {"logging": {"enabled": True}, "db": {"binding": "output"}}
    setattr(original, "_azure_functions_metadata", foreign)
    with pytest.warns(RuntimeWarning, match="correlation context"):
        handler = validate_http(response_model=PublicOutput)(original)
    signature = inspect.signature(handler)
    assert list(signature.parameters) == ["req", "output"]
    assert signature.return_annotation is inspect.Signature.empty
    assert handler.__annotations__ == {"output": Out[str]}
    assert not hasattr(handler, "__wrapped__")
    metadata = getattr(handler, "_azure_functions_metadata")
    assert metadata["logging"] == foreign["logging"]
    assert metadata["db"] == foreign["db"]
    output = NativeOut()
    response = handler(HttpRequest("GET", "http://localhost", body=b""), output=output)
    assert output.get() == "untouched"
    assert response.status_code == 201
    assert json.loads(response.get_body()) == {"value": 7}


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("failure", ["", "validation", "serialization"])
def test_outer_logging_sees_envelope_response_and_failure_context(
    asynchronous: bool, failure: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import Mock

    from azure_functions_validation import PydanticAdapter

    correlation: ContextVar[str] = ContextVar("response-correlation")
    observed = []
    adapter = PydanticAdapter()
    if failure == "serialization":
        monkeypatch.setattr(
            adapter, "serialize_response", Mock(side_effect=RuntimeError("private"))
        )

    def formatter(exc: Exception, status: int) -> dict[str, str]:
        return {"trace": correlation.get()}

    def result() -> ResponseSpec[dict[str, str] | dict[str, int]]:
        return ResponseSpec(
            content={"wrong": "private"} if failure == "validation" else {"value": 7},
            status_code=202,
            headers=[("X-Trace", correlation.get()), ("Set-Cookie", "a=1"), ("Set-Cookie", "b=2")],
        )

    @validate_http(response_model=PublicOutput, adapter=adapter, error_formatter=formatter)
    def sync(req: HttpRequest) -> ResponseSpec[dict[str, str] | dict[str, int]]:
        return result()

    @validate_http(response_model=PublicOutput, adapter=adapter, error_formatter=formatter)
    async def async_handler(req: HttpRequest) -> ResponseSpec[dict[str, str] | dict[str, int]]:
        return result()

    async def invoke() -> HttpResponse:
        response = await async_handler(HttpRequest("GET", "http://localhost", body=b""))
        assert isinstance(response, HttpResponse)
        return response

    def outer() -> HttpResponse:
        token = correlation.set("trace-617")
        try:
            response = (
                pytest.importorskip("anyio").run(invoke)
                if asynchronous
                else sync(HttpRequest("GET", "http://localhost", body=b""))
            )
            observed.append(
                (correlation.get(), response.status_code, list(response.headers.items()))
            )
            assert isinstance(response, HttpResponse)
            return response
        finally:
            correlation.reset(token)

    response = outer()
    assert observed == [("trace-617", 500 if failure else 202, list(response.headers.items()))]
    if failure:
        assert json.loads(response.get_body()) == {"trace": "trace-617"}
        assert response.headers.get("X-Trace") is None
    else:
        assert response.headers["X-Trace"] == "trace-617"
        assert response.headers.get_all("Set-Cookie") == ["a=1", "b=2"]


def test_envelope_annotation_and_runtime_status_leave_metadata_unchanged() -> None:
    @validate_http(response_model=PublicOutput, status_code=202)
    def ordinary(req: HttpRequest) -> PublicOutput:
        return PublicOutput(value=1)

    @validate_http(response_model=PublicOutput, status_code=202)
    def envelope(req: HttpRequest) -> ResponseSpec[PublicOutput]:
        return ResponseSpec(content=PublicOutput(value=1), status_code=201)

    expected = getattr(ordinary, "_azure_functions_metadata")["endpoint"]
    assert expected["version"] == 1
    assert set(expected["responses"]) == {"202"}
    assert getattr(envelope, "_azure_functions_metadata")["endpoint"] == expected
    assert envelope(HttpRequest("GET", "http://localhost", body=b"")).status_code == 201
    assert getattr(envelope, "_azure_functions_metadata")["endpoint"] == expected
