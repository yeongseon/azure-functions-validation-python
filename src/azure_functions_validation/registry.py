"""Global error handler registry for centralized error handling."""

from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Type

if TYPE_CHECKING:
    from azure.functions import HttpResponse
else:
    HttpResponse = Any

ErrorHandler = Callable[[Exception], HttpResponse]


class GlobalErrorHandlerRegistry:
    """Registry for global error handlers."""

    _handlers: Dict[type, ErrorHandler] = {}

    @classmethod
    def register(cls, exception_type: type, handler: ErrorHandler) -> None:
        cls._handlers[exception_type] = handler

    @classmethod
    def get_handler(cls, exception: Exception) -> Optional[ErrorHandler]:
        for registered_type, handler in cls._handlers.items():
            if isinstance(exception, registered_type):
                return handler
        return None

    @classmethod
    def clear(cls) -> None:
        cls._handlers.clear()


def register_global_error_handler(exception_type: Type[Exception], handler: ErrorHandler) -> None:
    """Register a global error handler for a specific exception type.

    Args:
        exception_type: Exception class to handle
        handler: Function that takes exception and returns HttpResponse
    """
    GlobalErrorHandlerRegistry.register(exception_type, handler)


def clear_global_error_handlers() -> None:
    """Clear all registered global error handlers (useful for testing)."""
    GlobalErrorHandlerRegistry.clear()
