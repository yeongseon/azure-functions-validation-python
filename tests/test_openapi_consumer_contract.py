import azure.functions as func
from azure_functions_openapi.bridge import scan_endpoint_metadata
from azure_functions_openapi.registry import OpenAPIRegistry
from pydantic import BaseModel

from azure_functions_validation import validate_http


def test_real_openapi_consumer_accepts_validation_endpoint_contract() -> None:
    class Payload(BaseModel):
        name: str

    app = func.FunctionApp()

    @app.route(route="contract", methods=["POST"])
    @validate_http(body=Payload, response_model=Payload)
    def handler(req: func.HttpRequest, body: Payload) -> Payload:
        return body

    registry = OpenAPIRegistry()
    scan_endpoint_metadata(app, registry=registry)
    entry = registry.get("post::/api/contract")
    assert entry is not None
    assert entry["request_body"]["properties"]["name"]["type"] == "string"
    assert entry["request_body_required"] is True
    assert 200 in entry["response"]
    assert 422 in entry["response"]
