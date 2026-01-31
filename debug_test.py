"""Debug script for testing empty body handling."""

from unittest.mock import Mock
from azure.functions import HttpRequest
from azure_functions_validation.adapter import PydanticAdapter
from pydantic import BaseModel, ValidationError


class TestModel(BaseModel):
    name: str


def debug_empty_body():
    adapter = PydanticAdapter()

    # Create mock request with empty body
    request = Mock(spec=HttpRequest)
    request.get_body.return_value = b""

    try:
        result = adapter.parse_body(request, TestModel)
        print(f"Unexpected success: {result}")
    except ValueError as e:
        print(f"ValueError: {e}")
        print(f"Type: {type(e)}")
    except ValidationError as e:
        print(f"ValidationError: {e}")
        print(f"Type: {type(e)}")
        print(f"Errors: {e.errors()}")
    except Exception as e:
        print(f"Other exception: {type(e).__name__}: {e}")


if __name__ == "__main__":
    debug_empty_body()
