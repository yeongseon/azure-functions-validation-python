"""Contract tests for the public validation-adapter conformance suite."""

from typing import Any

import pytest

from azure_functions_validation import PydanticAdapter
from azure_functions_validation.testing import AdapterConformanceTests


class TestPydanticAdapterConformance(AdapterConformanceTests):
    def make_adapter(self) -> PydanticAdapter:
        return PydanticAdapter()


class BrokenJsonAdapter(PydanticAdapter):
    def parse_body(self, req: Any, model: Any) -> Any:
        if req.get_body() == b"{invalid":
            raise ValueError("invalid JSON")
        return super().parse_body(req, model)


class BrokenAdapterConformance(AdapterConformanceTests):
    def make_adapter(self) -> BrokenJsonAdapter:
        return BrokenJsonAdapter()


def test_conformance_suite_rejects_wrong_malformed_input_exception() -> None:
    suite = BrokenAdapterConformance()

    with pytest.raises(AssertionError, match="MalformedRequestError"):
        suite.test_invalid_json_raises_malformed_request_error()
