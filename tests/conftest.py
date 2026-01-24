"""Test configuration and shared fixtures."""

from unittest.mock import Mock

from azure.functions import HttpRequest
import pytest

from azure_functions_validation._adapter import PydanticAdapter


@pytest.fixture
def adapter() -> PydanticAdapter:
    """Create adapter instance."""
    return PydanticAdapter()


@pytest.fixture
def mock_request() -> Mock:
    """Create mock HTTP request."""
    return Mock(spec=HttpRequest)
