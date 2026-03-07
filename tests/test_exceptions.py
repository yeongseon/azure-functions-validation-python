from azure_functions_validation.exceptions import ResponseValidationError


def test_response_validation_error_defaults() -> None:
    error = ResponseValidationError()

    assert str(error) == "Response validation error"
    assert error.message == "Response validation error"


def test_response_validation_error_custom_message() -> None:
    error = ResponseValidationError("Custom response error")

    assert str(error) == "Custom response error"
    assert error.message == "Custom response error"
