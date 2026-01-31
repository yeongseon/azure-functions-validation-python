"""Contract testing utilities for Azure Function handlers."""

from typing import Any, Callable, Type, Dict, Optional
from pydantic import BaseModel


def contract_test(
    request_model: Optional[Type[BaseModel]] = None,
    response_model: Optional[Type[BaseModel]] = None,
    allow_extra: bool = False,
):
    """Decorator for testing contract compliance of Azure Function handlers.

    Args:
        request_model: Optional Pydantic model for request validation
        response_model: Optional Pydantic model for response validation
        allow_extra: If True, allow extra fields in validation

    Returns:
        Decorated function that validates inputs/outputs
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = func(*args, **kwargs)

            if request_model is not None and "body" in kwargs:
                if isinstance(kwargs["body"], BaseModel):
                    try:
                        request_model.model_validate(kwargs["body"].model_dump())
                    except Exception as e:
                        raise AssertionError(f"Request validation failed: {e}")
                else:
                    request_model.model_validate(kwargs["body"])

            validation_result = {"success": True}

            if response_model is not None:
                if isinstance(result, BaseModel):
                    try:
                        response_model.model_validate(result.model_dump())
                    except Exception as e:
                        validation_result["success"] = False
                        validation_result["error"] = f"Response validation failed: {e}"
                elif isinstance(result, dict):
                    try:
                        response_model.model_validate(result)
                    except Exception as e:
                        validation_result["success"] = False
                        validation_result["error"] = f"Response validation failed: {e}"
                elif isinstance(result, list):
                    for item in result:
                        if isinstance(item, dict):
                            try:
                                response_model.model_validate(item)
                            except Exception as e:
                                validation_result["success"] = False
                                validation_result["error"] = f"Response validation failed: {e}"

            return validation_result

        return wrapper

    return decorator


def verify_contracts(
    function: Callable[..., Any],
    test_data: Dict[str, Any],
    request_model: Optional[Type[BaseModel]] = None,
    response_model: Optional[Type[BaseModel]] = None,
) -> Dict[str, Any]:
    """Verify that a function conforms to its contract models.

    Args:
        function: Function to test
        test_data: Test data for the function
        request_model: Optional Pydantic model for request
        response_model: Optional Pydantic model for response

    Returns:
        Dict with validation results
    """
    result = {}

    try:
        output = function(**test_data)

        if response_model is not None:
            if isinstance(output, BaseModel):
                validated = response_model.model_validate(output.model_dump())
                result["response_valid"] = True
                result["response_data"] = validated.model_dump()
            elif isinstance(output, dict):
                validated = response_model.model_validate(output)
                result["response_valid"] = True
                result["response_data"] = validated.model_dump()
            else:
                result["response_valid"] = False
                result["response_type"] = type(output).__name__
        else:
            result["response_valid"] = None
            result["response_data"] = output

        result["success"] = result.get("response_valid", True)
    except AssertionError as e:
        result["success"] = False
        result["error"] = str(e)
    except Exception as e:
        result["success"] = False
        result["error"] = f"Unexpected error: {e}"

    return result
