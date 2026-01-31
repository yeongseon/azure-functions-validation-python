"""Contract testing utilities for Azure Function handlers."""

from typing import Any, Callable, Dict, Optional, Type

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
        Decorated function that validates inputs/outputs and returns validation result dict
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Dict[str, Any]]:
        def wrapper(*args: Any, **kwargs: Any) -> Dict[str, Any]:
            validation_result: Dict[str, Any] = {"success": True}

            try:
                if request_model is not None and "body" in kwargs:
                    body_value = kwargs["body"]
                    if isinstance(body_value, dict):
                        try:
                            validated_body = request_model.model_validate(body_value)
                            kwargs["body"] = validated_body
                            validation_result["request_valid"] = True
                        except Exception as e:
                            validation_result["success"] = False
                            validation_result["request_valid"] = False
                            validation_result["error"] = f"Request validation failed: {e}"
                            return validation_result
                    elif isinstance(body_value, BaseModel):
                        try:
                            request_model.model_validate(body_value.model_dump())
                            validation_result["request_valid"] = True
                        except Exception as e:
                            validation_result["success"] = False
                            validation_result["request_valid"] = False
                            validation_result["error"] = f"Request validation failed: {e}"
                            return validation_result

                result = func(*args, **kwargs)

                if response_model is not None:
                    if isinstance(result, BaseModel):
                        try:
                            response_model.model_validate(result.model_dump())
                            validation_result["response_valid"] = True
                        except Exception as e:
                            validation_result["success"] = False
                            validation_result["response_valid"] = False
                            validation_result["error"] = f"Response validation failed: {e}"
                    elif isinstance(result, dict):
                        try:
                            response_model.model_validate(result)
                            validation_result["response_valid"] = True
                        except Exception as e:
                            validation_result["success"] = False
                            validation_result["response_valid"] = False
                            validation_result["error"] = f"Response validation failed: {e}"
                    elif isinstance(result, list):
                        validation_result["response_valid"] = True
                        for item in result:
                            if isinstance(item, dict):
                                try:
                                    response_model.model_validate(item)
                                except Exception as e:
                                    validation_result["success"] = False
                                    validation_result["response_valid"] = False
                                    validation_result["error"] = f"Response validation failed: {e}"
                                    break
                else:
                    validation_result["response_valid"] = None

                if (
                    validation_result.get("request_valid") is True
                    and validation_result.get("response_valid") is not False
                ):
                    validation_result["success"] = True
            except AssertionError as e:
                validation_result["success"] = False
                validation_result["error"] = str(e)
            except Exception as e:
                validation_result["success"] = False
                validation_result["error"] = f"Unexpected error: {e}"

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
        test_data: Test data for function
        request_model: Optional Pydantic model for request
        response_model: Optional Pydantic model for response

    Returns:
        Dict with validation results
    """
    from pydantic import ValidationError as PydanticValidationError

    result: Dict[str, Any] = {}

    try:
        if request_model is not None:
            for key, value in test_data.items():
                if isinstance(value, (dict, list)):
                    try:
                        if isinstance(value, dict):
                            request_model.model_validate(value)
                            result["request_valid"] = True
                        else:
                            for item in value:
                                request_model.model_validate(item)
                            result["request_valid"] = True
                    except PydanticValidationError as e:
                        result["request_valid"] = False
                        result["success"] = False
                        result["error"] = f"Request validation failed: {e}"
                        return result

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

        if (
            result.get("request_valid", True) is False
            or result.get("response_valid", True) is False
        ):
            result["success"] = False
        else:
            result["success"] = result.get("response_valid", True)
    except AssertionError as e:
        result["success"] = False
        result["error"] = str(e)
    except PydanticValidationError as e:
        result["success"] = False
        result["error"] = f"Validation failed: {e}"
    except Exception as e:
        result["success"] = False
        result["error"] = f"Unexpected error: {e}"

    return result
