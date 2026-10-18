"""Custom ``trigger_arg_name`` must survive ``@validate_http`` (issue #538).

``WorkerCompat._override_signature()`` used to hardcode the worker-visible
request parameter's name as ``"req"``, regardless of the handler's actual
request parameter name. A route declared with
``@app.route(trigger_arg_name="request")`` keeps its SDK binding named
``"request"``, so the worker-visible callable and the binding disagreed --
exactly the mismatch the real worker's ``validate_function_params()``
rejects with ``FunctionLoadError`` (see the issue's own reference to the
pinned worker source). A direct unit invocation of the wrapper still
succeeded either way, which is why this previously went unnoticed: the SDK's
own ``FunctionApp.get_functions()`` never performs the worker's parameter
validation, so these tests instead replicate the worker's own invariant
directly against the real ``azure.functions`` SDK's binding introspection
(``FunctionBuilder.build().get_bindings()`` / ``get_user_function()``) --
not just checking that indexing produced a non-empty list.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import inspect
import json
from typing import Any

import azure.functions as func
from azure.functions.decorators.function_app import Function
from pydantic import BaseModel
import pytest

from azure_functions_validation import validate_http


class _Body(BaseModel):
    value: int


def _registered(app: func.FunctionApp) -> Function:
    functions = app.get_functions()
    assert len(functions) >= 1, "worker indexed zero functions"
    return functions[0]


def _assert_signature_matches_bindings(
    app: func.FunctionApp,
) -> tuple[Callable[..., Any], set[str]]:
    """Replicate the worker's own name-binding invariant (#538).

    The real worker's ``validate_function_params()`` rejects a callable whose
    Python parameter names disagree with its SDK binding names. Returns the
    user function and its signature's parameter names for further assertions.
    """
    registered = _registered(app)
    wrapper = registered.get_user_function()
    signature_names = set(inspect.signature(wrapper).parameters)
    binding_names = {b.name for b in registered.get_bindings() if b.name != "$return"}
    assert signature_names == binding_names, (
        f"worker-visible signature {sorted(signature_names)} disagrees with "
        f"SDK binding names {sorted(binding_names)} -- the real worker would "
        "reject this with FunctionLoadError"
    )
    return wrapper, signature_names


class TestCustomTriggerArgName:
    def test_sync_custom_name_signature_matches_binding(self) -> None:
        app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

        @app.route(route="probe", trigger_arg_name="request", methods=["POST"])
        @validate_http(body=_Body)
        def handler(request: func.HttpRequest, body: _Body) -> dict[str, int]:
            return body.model_dump()

        wrapper, names = _assert_signature_matches_bindings(app)
        assert names == {"request"}

    def test_sync_custom_name_both_invocation_styles_work(self) -> None:
        app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

        @app.route(route="probe", trigger_arg_name="request", methods=["POST"])
        @validate_http(body=_Body)
        def handler(request: func.HttpRequest, body: _Body) -> dict[str, int]:
            return body.model_dump()

        wrapper = _registered(app).get_user_function()
        req = func.HttpRequest(
            method="POST",
            url="http://localhost/api/probe",
            headers={},
            params={},
            body=b'{"value": 1}',
        )

        by_original_name = wrapper(request=req)
        assert by_original_name.status_code == 200
        assert json.loads(by_original_name.get_body()) == {"value": 1}

        positional = wrapper(req)
        assert positional.status_code == 200
        assert json.loads(positional.get_body()) == {"value": 1}

    def test_async_custom_name_signature_matches_binding_and_invokes(self) -> None:
        app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

        @app.route(route="probe", trigger_arg_name="myreq", methods=["POST"])
        @validate_http(body=_Body)
        async def handler(myreq: func.HttpRequest, body: _Body) -> dict[str, int]:
            return body.model_dump()

        wrapper, names = _assert_signature_matches_bindings(app)
        assert names == {"myreq"}

        req = func.HttpRequest(
            method="POST",
            url="http://localhost/api/probe",
            headers={},
            params={},
            body=b'{"value": 2}',
        )
        response = asyncio.run(wrapper(myreq=req))
        assert response.status_code == 200
        assert json.loads(response.get_body()) == {"value": 2}

    def test_default_req_name_is_unaffected(self) -> None:
        """Regression guard: no custom trigger_arg_name still exposes "req"."""
        app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

        @app.route(route="probe", methods=["POST"])
        @validate_http(body=_Body)
        def handler(req: func.HttpRequest, body: _Body) -> dict[str, int]:
            return body.model_dump()

        wrapper, names = _assert_signature_matches_bindings(app)
        assert names == {"req"}
        assert "req" not in wrapper.__annotations__

    def test_custom_name_with_output_binding_passthrough(self) -> None:
        """Extra input/output bindings stay visible alongside a renamed request param."""
        app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

        @app.route(route="probe", trigger_arg_name="request", methods=["POST"])
        @app.queue_output(arg_name="out_msg", queue_name="q", connection="AzureWebJobsStorage")
        @validate_http(body=_Body)
        def handler(
            request: func.HttpRequest, body: _Body, out_msg: func.Out[str]
        ) -> dict[str, int]:
            out_msg.set(str(body.value))
            return body.model_dump()

        wrapper, names = _assert_signature_matches_bindings(app)
        assert names == {"request", "out_msg"}
        assert wrapper.__annotations__.get("out_msg") is func.Out[str]

    def test_validation_injected_params_stay_hidden_with_custom_name(self) -> None:
        """body/query/path/headers never appear in the worker-visible signature."""
        app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

        class _Query(BaseModel):
            limit: int = 10

        @app.route(route="probe", trigger_arg_name="request", methods=["GET"])
        @validate_http(query=_Query)
        def handler(request: func.HttpRequest, query: _Query) -> dict[str, int]:
            return query.model_dump()

        _wrapper, names = _assert_signature_matches_bindings(app)
        assert names == {"request"}
        assert "query" not in names

    @pytest.mark.parametrize("custom_name", ["request", "myreq", "http_req"])
    def test_signature_matches_binding_for_various_custom_names(self, custom_name: str) -> None:
        app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

        # Build the handler with the parameter dynamically named *custom_name*,
        # since Python syntax cannot parametrize a def's own parameter name.
        namespace: dict[str, object] = {"validate_http": validate_http, "_Body": _Body, "app": app}
        exec(  # noqa: S102
            f"""
@app.route(route="probe", trigger_arg_name={custom_name!r}, methods=["POST"])
@validate_http(body=_Body)
def handler({custom_name}, body):
    return body.model_dump()
""",
            namespace,
        )

        _wrapper, names = _assert_signature_matches_bindings(app)
        assert names == {custom_name}
