"""Local logging-order contract; not a sibling logging-release integration."""

from collections.abc import Callable
from contextvars import ContextVar
import inspect
import json
from typing import Any

import azure.functions as func
import pytest

from azure_functions_validation import validate_http

_active: ContextVar[bool] = ContextVar("active", default=False)


class RecordingOut(func.Out[str]):
    def __init__(self) -> None:
        self.value = ""

    def set(self, val: str) -> None:
        self.value = val

    def get(self) -> str:
        return self.value


def _outer_logging(handler: Callable[..., Any]) -> Callable[..., Any]:
    def wrapper(req: Any = None, **kwargs: Any) -> Any:
        token = _active.set(True)
        try:
            return handler(req, **kwargs) if req is not None else handler(**kwargs)
        finally:
            _active.reset(token)

    setattr(wrapper, "__signature__", inspect.signature(handler))
    wrapper.__annotations__ = dict(handler.__annotations__)
    setattr(
        wrapper,
        "_azure_functions_metadata",
        {
            **getattr(handler, "_azure_functions_metadata"),
            "logging": {"version": 1},
        },
    )
    return wrapper


@pytest.mark.parametrize("page", ["2", "bad"], ids=["successful-validation", "failed-validation"])
def test_outer_logging_context_covers_validation_and_handler(page: str) -> None:
    observed: list[bool] = []

    def formatter(exc: Exception, status: int) -> dict[str, Any]:
        observed.append(_active.get())
        return {"status": status}

    app = func.FunctionApp()

    def original(request: func.HttpRequest, out_msg: func.Out[str], *, page: int) -> dict[str, int]:
        observed.append(_active.get())
        out_msg.set(str(page))
        return {"page": page}

    foreign = {"db": {"version": 1}, "arbitrary": object()}
    setattr(original, "_azure_functions_metadata", foreign)
    validated = validate_http(query_params={"page": int}, error_formatter=formatter)(original)
    wrapped = _outer_logging(validated)
    app.route(route="composition", trigger_arg_name="request")(
        app.queue_output(arg_name="out_msg", queue_name="q", connection="AzureWebJobsStorage")(
            wrapped
        )
    )
    registered = app.get_functions()[0]
    assert set(inspect.signature(wrapped).parameters) == {
        binding.name for binding in registered.get_bindings() if binding.name != "$return"
    }
    assert wrapped.__annotations__ == {"out_msg": func.Out[str]}
    metadata = getattr(wrapped, "_azure_functions_metadata")
    assert metadata["db"] is foreign["db"]
    assert metadata["arbitrary"] is foreign["arbitrary"]
    assert set(metadata) == {"db", "arbitrary", "validation", "endpoint", "logging"}
    assert getattr(original, "_azure_functions_metadata") is foreign
    output = RecordingOut()
    response = wrapped(
        request=func.HttpRequest(
            method="GET", url=f"http://localhost/?page={page}", params={"page": page}, body=b""
        ),
        out_msg=output,
    )
    assert observed == [True]
    assert _active.get() is False
    assert response.status_code == (200 if page == "2" else 422)
    assert json.loads(response.get_body()) == ({"page": 2} if page == "2" else {"status": 422})
    assert output.get() == ("2" if page == "2" else "")
