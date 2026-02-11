"""Tests for contract testing utilities."""

from pydantic import BaseModel, Field

from azure_functions_validation import contract_test, verify_contracts


class TestContractTestDecorator:
    """Tests for @contract_test decorator."""

    def test_request_validation_passes(self) -> None:
        """Test that valid request passes contract test."""

        class Request(BaseModel):
            name: str = Field(min_length=3)
            age: int = Field(ge=0, le=150)

        @contract_test(request_model=Request)
        def handler(body: Request) -> dict[str, object]:
            return {"message": "ok"}

        result = handler(body={"name": "Alice", "age": 30})
        assert result["success"] is True
        assert result["request_valid"] is True

    def test_request_validation_fails(self) -> None:
        """Test that invalid request fails contract test."""

        class Request(BaseModel):
            name: str = Field(min_length=3)
            age: int = Field(ge=0, le=150)

        @contract_test(request_model=Request)
        def handler(body: Request) -> dict[str, object]:
            return {"message": "ok"}

        result = handler(body={"name": "Bo", "age": 30})

        assert result["success"] is False
        assert "error" in result

    def test_response_validation_passes(self) -> None:
        """Test that valid response passes contract test."""

        class Request(BaseModel):
            name: str

        class Response(BaseModel):
            message: str
            status: str = "success"

        @contract_test(request_model=Request, response_model=Response)
        def handler(body: Request) -> dict[str, object]:
            return {"message": "Hello", "status": "success"}

        result = handler(body={"name": "Charlie"})

        assert result["success"] is True
        assert result["response_valid"] is True

    def test_response_validation_fails(self) -> None:
        """Test that invalid response fails contract test."""

        class Request(BaseModel):
            name: str

        class Response(BaseModel):
            message: str
            status: str

        @contract_test(request_model=Request, response_model=Response)
        def handler(body: Request) -> dict[str, object]:
            return {"message": "ok"}

        result = handler(body={"name": "David"})

        assert result["success"] is False
        assert "error" in result

    def test_dict_response_validation(self) -> None:
        """Test dict response validation against model."""

        class Request(BaseModel):
            name: str

        class Response(BaseModel):
            message: str

        @contract_test(request_model=Request, response_model=Response)
        def handler(body: Request) -> dict[str, object]:
            return {"message": "Hello"}

        result = handler(body={"name": "Eve"})

        assert result["success"] is True
        assert result["response_valid"] is True

    def test_allow_extra_fields(self) -> None:
        """Test that extra fields in dict response are allowed by default."""

        class Request(BaseModel):
            name: str

        class Response(BaseModel):
            message: str

        @contract_test(request_model=Request, response_model=Response)
        def handler(body: Request) -> dict[str, object]:
            return {"message": "Hello", "extra": "field"}

        result = handler(body={"name": "Frank"})

        assert result["success"] is True
        assert result["response_valid"] is True

    def test_request_body_as_model_instance(self) -> None:
        """Test request validation when body is already a BaseModel instance."""

        class Request(BaseModel):
            name: str
            age: int

        @contract_test(request_model=Request)
        def handler(body: Request) -> dict[str, object]:
            return {"message": "ok"}

        result = handler(body=Request(name="Grace", age=29))

        assert result["success"] is True
        assert result["request_valid"] is True

    def test_response_validation_with_model_instance(self) -> None:
        """Test response validation when handler returns a BaseModel instance."""

        class Request(BaseModel):
            name: str

        class Response(BaseModel):
            message: str

        @contract_test(request_model=Request, response_model=Response)
        def handler(body: Request) -> Response:
            return Response(message="hi")

        result = handler(body={"name": "Hana"})

        assert result["success"] is True
        assert result["response_valid"] is True

    def test_response_validation_with_list(self) -> None:
        """Test list response validation against a model."""

        class Request(BaseModel):
            name: str

        class Response(BaseModel):
            message: str

        @contract_test(request_model=Request, response_model=Response)
        def handler(body: Request) -> list[dict[str, object]]:
            return [{"message": "hello"}, {"message": "world"}]

        result = handler(body={"name": "Ivy"})

        assert result["success"] is True
        assert result["response_valid"] is True

    def test_response_validation_with_list_failure(self) -> None:
        """Test list response validation fails on invalid item."""

        class Request(BaseModel):
            name: str

        class Response(BaseModel):
            message: str

        @contract_test(request_model=Request, response_model=Response)
        def handler(body: Request) -> list[dict[str, object]]:
            return [{"message": "ok"}, {"nope": "missing"}]

        result = handler(body={"name": "Jin"})

        assert result["success"] is False
        assert result["response_valid"] is False

    def test_unexpected_exception_path(self) -> None:
        """Test unexpected exception handling in decorator wrapper."""

        class Request(BaseModel):
            name: str

        @contract_test(request_model=Request)
        def handler(body: Request) -> dict[str, object]:
            raise RuntimeError("boom")

        result = handler(body={"name": "Kyle"})

        assert result["success"] is False
        assert "Unexpected error" in str(result.get("error"))


class TestVerifyContracts:
    """Tests for verify_contracts function."""

    def test_verify_valid_function(self) -> None:
        """Test verification of valid function."""

        class Request(BaseModel):
            name: str

        class Response(BaseModel):
            message: str

        def handler(body: Request) -> Response:
            return Response(message="ok")

        result = verify_contracts(
            handler,
            {"body": {"name": "Alice"}},
            request_model=Request,
            response_model=Response,
        )

        assert result["success"] is True

    def test_verify_invalid_request(self) -> None:
        """Test verification detects invalid request."""

        class Request(BaseModel):
            name: str
            age: int = Field(ge=0)

        def handler(body: Request) -> dict[str, object]:
            return {"message": "ok", "age": 30}

        result = verify_contracts(
            handler,
            {"body": {"name": "Bob", "age": "invalid"}},
            request_model=Request,
        )

        assert result["success"] is False
        assert "error" in result

    def test_verify_invalid_response(self) -> None:
        """Test verification detects invalid response."""

        from pydantic import ConfigDict

        class Request(BaseModel):
            name: str

        class Response(BaseModel):
            model_config = ConfigDict(extra="forbid")
            message: str

        def handler(body: Request) -> dict[str, object]:
            return {"message": "ok", "extra": "field"}

        result = verify_contracts(
            handler,
            {"body": {"name": "Charlie"}},
            request_model=Request,
            response_model=Response,
        )

        assert result["success"] is False
        assert "error" in result

    def test_verify_response_without_model(self) -> None:
        """Test verification when no response model is provided."""

        class Request(BaseModel):
            name: str

        def handler(body: Request) -> dict[str, object]:
            return {"message": "ok"}

        result = verify_contracts(handler, {"body": {"name": "Lina"}}, request_model=Request)

        assert result["success"] is True
        assert result["response_valid"] is None
        assert result["response_data"] == {"message": "ok"}

    def test_verify_request_list_payload(self) -> None:
        """Test verification when request data contains lists of items."""

        class Request(BaseModel):
            name: str

        def handler(body: Request) -> dict[str, object]:
            return {"message": "ok"}

        result = verify_contracts(
            handler,
            {"body": [{"name": "Mina"}, {"name": "Nora"}]},
            request_model=Request,
        )

        assert result["success"] is True
        assert result["request_valid"] is True

    def test_verify_response_type_mismatch(self) -> None:
        """Test verification when response type is unsupported."""

        class Request(BaseModel):
            name: str

        class Response(BaseModel):
            message: str

        def handler(body: Request) -> list[str]:
            return ["not", "a", "dict"]

        result = verify_contracts(
            handler,
            {"body": {"name": "Owen"}},
            request_model=Request,
            response_model=Response,
        )

        assert result["success"] is False
        assert result["response_valid"] is False
