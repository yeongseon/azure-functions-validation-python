"""Tests for @validate_http decorator configuration (decoration-time errors).

Runtime pipeline behaviour (parsing, response building) is tested in
``test_pipeline.py``.  This file only covers configuration-time validation
that happens when ``@validate_http(...)`` is applied to a function.
"""

from azure.functions import HttpRequest, HttpResponse
from pydantic import BaseModel, Field
import pytest

from azure_functions_validation import validate_http

# ---------------------------------------------------------------------------
# Minimal models used by configuration tests
# ---------------------------------------------------------------------------


class UserModel(BaseModel):
    name: str = Field(min_length=3, max_length=50)
    age: int = Field(ge=0, le=150)


class QueryModel(BaseModel):
    limit: int = Field(ge=1, le=100, default=10)
    offset: int = Field(ge=0, default=0)


class PathModel(BaseModel):
    user_id: int = Field(ge=1)


class HeaderModel(BaseModel):
    authorization: str
    user_agent: str = Field(default="unknown")


# ---------------------------------------------------------------------------
# Configuration error tests
# ---------------------------------------------------------------------------


class TestConfigurationErrors:
    """Tests for decorator configuration errors."""

    def test_request_model_with_body_conflict(self) -> None:
        """Test ValueError when request_model and body are both provided."""

        with pytest.raises(
            ValueError, match="Cannot use request_model together with body/query/path/headers"
        ):

            @validate_http(request_model=UserModel, body=UserModel)
            def handler(req: HttpRequest) -> HttpResponse:
                return HttpResponse("ok")

    def test_keyword_only_request_parameter_is_rejected(self) -> None:
        """Test ValueError when the request parameter is not positional."""

        with pytest.raises(
            ValueError,
            match="must accept an HttpRequest parameter as its first positional argument",
        ):

            @validate_http(body=UserModel)
            def handler(*, request: HttpRequest) -> HttpResponse:
                return HttpResponse("ok")

    def test_request_param_name_conflicts_with_body_injection(self) -> None:
        """Test ValueError when the first positional param is named 'body' and body= is set."""

        with pytest.raises(
            ValueError,
            match="conflicts with a @validate_http injected parameter of the same name",
        ):

            @validate_http(body=UserModel)
            def handler(body: HttpRequest, user: UserModel) -> HttpResponse:
                return HttpResponse("ok")

    def test_request_param_name_conflicts_with_query_injection(self) -> None:
        """Test ValueError when the first positional param is named 'query' and query= is set."""

        with pytest.raises(
            ValueError,
            match="conflicts with a @validate_http injected parameter of the same name",
        ):

            @validate_http(query=QueryModel)
            def handler(query: HttpRequest) -> HttpResponse:
                return HttpResponse("ok")

    def test_request_param_name_conflicts_with_path_injection(self) -> None:
        """Test ValueError when the first positional param is named 'path' and path= is set."""

        with pytest.raises(
            ValueError,
            match="conflicts with a @validate_http injected parameter of the same name",
        ):

            @validate_http(path=PathModel)
            def handler(path: HttpRequest) -> HttpResponse:
                return HttpResponse("ok")

    def test_request_param_name_conflicts_with_headers_injection(self) -> None:
        """Test a conflict when the first positional parameter is named `headers`."""

        with pytest.raises(
            ValueError,
            match="conflicts with a @validate_http injected parameter of the same name",
        ):

            @validate_http(headers=HeaderModel)
            def handler(headers: HttpRequest) -> HttpResponse:
                return HttpResponse("ok")

    def test_request_param_named_body_without_injection_is_allowed(self) -> None:
        """No error when param is named 'body' but no body= is configured."""

        # Should not raise – body injection is not enabled
        @validate_http()
        def handler(body: HttpRequest) -> HttpResponse:
            return HttpResponse("ok")

    def test_safe_request_param_names_are_allowed(self) -> None:
        """Standard param names like 'req' / 'request' / 'http_request' must not raise."""

        for name in ("req", "request", "http_request"):

            @validate_http(body=UserModel)
            def handler(req: HttpRequest, body: UserModel) -> HttpResponse:  # noqa: F811
                return HttpResponse("ok")


class TestValidationNamespace:
    """Tests for metadata exposure on decorated functions."""

    def test_metadata_attached_with_body(self) -> None:
        """Decorated function exposes body model in metadata."""

        @validate_http(body=UserModel)
        def handler(req: HttpRequest, body: UserModel) -> HttpResponse:
            return HttpResponse("ok")

        meta = getattr(handler, "_azure_functions_metadata", None)
        assert meta is not None
        assert "validation" in meta
        validation = meta["validation"]
        assert validation["body"] is UserModel
        assert validation["query"] is None
        assert validation["path"] is None
        assert validation["headers"] is None
        assert validation["response_model"] is None

    def test_metadata_attached_with_all_params(self) -> None:
        """Decorated function exposes all configured models."""

        @validate_http(
            body=UserModel,
            query=QueryModel,
            path=PathModel,
            headers=HeaderModel,
            response_model=UserModel,
        )
        def handler(
            req: HttpRequest,
            body: UserModel,
            query: QueryModel,
            path: PathModel,
            headers: HeaderModel,
        ) -> HttpResponse:
            return HttpResponse("ok")

        meta = getattr(handler, "_azure_functions_metadata", None)
        assert meta is not None
        validation = meta["validation"]
        assert validation["body"] is UserModel
        assert validation["query"] is QueryModel
        assert validation["path"] is PathModel
        assert validation["headers"] is HeaderModel
        assert validation["response_model"] is UserModel

    def test_metadata_with_request_model_shorthand(self) -> None:
        """request_model shorthand maps to body in metadata."""

        @validate_http(request_model=UserModel)
        def handler(req: HttpRequest, body: UserModel) -> HttpResponse:
            return HttpResponse("ok")

        meta = getattr(handler, "_azure_functions_metadata", None)
        assert meta is not None
        assert meta["validation"]["body"] is UserModel

    def test_metadata_none_on_undecorated_function(self) -> None:
        """Non-decorated function has no metadata."""

        def handler(req: HttpRequest) -> HttpResponse:
            return HttpResponse("ok")

        assert getattr(handler, "_azure_functions_metadata", None) is None

    def test_metadata_with_response_model_only(self) -> None:
        """Metadata correctly captures response_model without request models."""

        @validate_http(response_model=UserModel)
        def handler(req: HttpRequest) -> dict[str, object]:
            return {"name": "Alice", "age": 30}

        meta = getattr(handler, "_azure_functions_metadata", None)
        assert meta is not None
        validation = meta["validation"]
        assert validation["body"] is None
        assert validation["response_model"] is UserModel

    def test_metadata_on_async_handler(self) -> None:
        """Async handlers also expose metadata."""

        @validate_http(body=UserModel, response_model=UserModel)
        async def handler(req: HttpRequest, body: UserModel) -> dict[str, object]:
            return {"name": body.name, "age": body.age}

        meta = getattr(handler, "_azure_functions_metadata", None)
        assert meta is not None
        validation = meta["validation"]
        assert validation["body"] is UserModel
        assert validation["response_model"] is UserModel
