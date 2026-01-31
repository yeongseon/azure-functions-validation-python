"""Tests for contract testing utilities."""

from pydantic import BaseModel, Field

from azure_functions_validation import contract_test, verify_contracts


class TestContractTestDecorator:
    """Tests for @contract_test decorator."""

    def test_request_validation_passes(self):
        """Test that valid request passes contract test."""

        class Request(BaseModel):
            name: str = Field(min_length=3)
            age: int = Field(ge=0, le=150)

        @contract_test(request_model=Request)
        def handler(body: Request) -> dict:
            return {"message": "ok"}

        result = handler(body={"name": "Alice", "age": 30})
        assert result["success"] is True
        assert result["request_valid"] is True

    def test_request_validation_fails(self):
        """Test that invalid request fails contract test."""

        class Request(BaseModel):
            name: str = Field(min_length=3)
            age: int = Field(ge=0, le=150)

        @contract_test(request_model=Request)
        def handler(body: Request) -> dict:
            return {"message": "ok"}

        result = handler(body={"name": "Bo", "age": 30})

        assert result["success"] is False
        assert "error" in result

    def test_response_validation_passes(self):
        """Test that valid response passes contract test."""

        class Request(BaseModel):
            name: str

        class Response(BaseModel):
            message: str
            status: str = "success"

        @contract_test(request_model=Request, response_model=Response)
        def handler(body: Request) -> dict:
            return {"message": "Hello", "status": "success"}

        result = handler(body={"name": "Charlie"})

        assert result["success"] is True
        assert result["response_valid"] is True

    def test_response_validation_fails(self):
        """Test that invalid response fails contract test."""

        class Request(BaseModel):
            name: str

        class Response(BaseModel):
            message: str
            status: str

        @contract_test(request_model=Request, response_model=Response)
        def handler(body: Request) -> dict:
            return {"message": "ok"}

        result = handler(body={"name": "David"})

        assert result["success"] is False
        assert "error" in result

    def test_dict_response_validation(self):
        """Test dict response validation against model."""

        class Request(BaseModel):
            name: str

        class Response(BaseModel):
            message: str

        @contract_test(request_model=Request, response_model=Response)
        def handler(body: Request) -> dict:
            return {"message": "Hello"}

        result = handler(body={"name": "Eve"})

        assert result["success"] is True
        assert result["response_valid"] is True

    def test_allow_extra_fields(self):
        """Test that extra fields in dict response are allowed by default."""

        class Request(BaseModel):
            name: str

        class Response(BaseModel):
            message: str

        @contract_test(request_model=Request, response_model=Response)
        def handler(body: Request) -> dict:
            return {"message": "Hello", "extra": "field"}

        result = handler(body={"name": "Frank"})

        assert result["success"] is True
        assert result["response_valid"] is True


class TestVerifyContracts:
    """Tests for verify_contracts function."""

    def test_verify_valid_function(self):
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

    def test_verify_invalid_request(self):
        """Test verification detects invalid request."""

        class Request(BaseModel):
            name: str
            age: int = Field(ge=0)

        def handler(body: Request) -> dict:
            return {"message": "ok", "age": 30}

        result = verify_contracts(
            handler,
            {"body": {"name": "Bob", "age": "invalid"}},
            request_model=Request,
        )

        assert result["success"] is False
        assert "error" in result

    def test_verify_invalid_response(self):
        """Test verification detects invalid response."""

        from pydantic import ConfigDict

        class Request(BaseModel):
            name: str

        class Response(BaseModel):
            model_config = ConfigDict(extra="forbid")
            message: str

        def handler(body: Request) -> dict:
            return {"message": "ok", "extra": "field"}

        result = verify_contracts(
            handler,
            {"body": {"name": "Charlie"}},
            request_model=Request,
            response_model=Response,
        )

        assert result["success"] is False
        assert "error" in result
