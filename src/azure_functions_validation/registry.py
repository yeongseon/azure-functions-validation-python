"""Global error handler registry for centralized error handling."""

from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Type

if TYPE_CHECKING:
    from azure.functions import HttpResponse
else:
    HttpResponse = Any

ErrorHandler = Callable[[Exception], HttpResponse]


class GlobalErrorHandlerRegistry:
    """Registry for global error handlers.

    Handlers are matched by ``isinstance`` check against the raised exception.
    When multiple registered types match (e.g. both ``ValueError`` and
    ``Exception``), the **most specific** type — the one deepest in the
    exception's MRO — is preferred.  This lets callers register a broad
    fallback (``Exception``) without shadowing more specific handlers.
    """

    _handlers: Dict[type, ErrorHandler] = {}

    @classmethod
    def register(cls, exception_type: type, handler: ErrorHandler) -> None:
        cls._handlers[exception_type] = handler

    @classmethod
    def get_handler(cls, exception: Exception) -> Optional[ErrorHandler]:
        """Return the handler registered for the most specific matching type.

        If several registered types satisfy ``isinstance(exception, t)``, the
        one appearing latest in ``type(exception).__mro__`` is considered the
        *least* specific; the one appearing earliest is the *most* specific.
        """
        best_handler: Optional[ErrorHandler] = None
        best_specificity: int = -1
        exc_mro = type(exception).__mro__
        for registered_type, handler in cls._handlers.items():
            if isinstance(exception, registered_type):
                try:
                    specificity = len(exc_mro) - exc_mro.index(registered_type)
                except ValueError:
                    specificity = 0
                if specificity > best_specificity:
                    best_specificity = specificity
                    best_handler = handler
        return best_handler

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
