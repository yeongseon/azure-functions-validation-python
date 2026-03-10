"""Dedicated tests for GlobalErrorHandlerRegistry."""


from azure.functions import HttpResponse

from azure_functions_validation.registry import (
    GlobalErrorHandlerRegistry,
    clear_global_error_handlers,
    register_global_error_handler,
)


class TestGlobalErrorHandlerRegistry:
    """Tests for the GlobalErrorHandlerRegistry class."""

    def setup_method(self) -> None:
        """Clear handlers before each test."""
        GlobalErrorHandlerRegistry.clear()

    def teardown_method(self) -> None:
        """Clear handlers after each test."""
        GlobalErrorHandlerRegistry.clear()

    def test_register_handler(self) -> None:
        """Test registering a handler for an exception type."""

        def handler(exc: Exception) -> HttpResponse:
            return HttpResponse("handled")

        GlobalErrorHandlerRegistry.register(ValueError, handler)
        assert len(GlobalErrorHandlerRegistry._handlers) == 1
        assert ValueError in GlobalErrorHandlerRegistry._handlers

    def test_get_handler_exact_match(self) -> None:
        """Test getting handler for exact exception type."""

        def handler(exc: Exception) -> HttpResponse:
            return HttpResponse("handled")

        GlobalErrorHandlerRegistry.register(ValueError, handler)
        result = GlobalErrorHandlerRegistry.get_handler(ValueError("test"))
        assert result is handler

    def test_get_handler_subclass_match(self) -> None:
        """Test getting handler for exception subclass via isinstance."""

        def handler(exc: Exception) -> HttpResponse:
            return HttpResponse("handled")

        GlobalErrorHandlerRegistry.register(Exception, handler)
        # ValueError is a subclass of Exception
        result = GlobalErrorHandlerRegistry.get_handler(ValueError("test"))
        assert result is handler

    def test_get_handler_no_match(self) -> None:
        """Test getting handler when no match exists."""

        def handler(exc: Exception) -> HttpResponse:
            return HttpResponse("handled")

        GlobalErrorHandlerRegistry.register(TypeError, handler)
        result = GlobalErrorHandlerRegistry.get_handler(ValueError("test"))
        assert result is None

    def test_get_handler_empty_registry(self) -> None:
        """Test getting handler from empty registry."""
        result = GlobalErrorHandlerRegistry.get_handler(ValueError("test"))
        assert result is None

    def test_clear_removes_all_handlers(self) -> None:
        """Test clearing all registered handlers."""

        def handler(exc: Exception) -> HttpResponse:
            return HttpResponse("handled")

        GlobalErrorHandlerRegistry.register(ValueError, handler)
        GlobalErrorHandlerRegistry.register(TypeError, handler)
        assert len(GlobalErrorHandlerRegistry._handlers) == 2

        GlobalErrorHandlerRegistry.clear()
        assert len(GlobalErrorHandlerRegistry._handlers) == 0

    def test_register_overwrites_existing(self) -> None:
        """Test that registering for same type overwrites."""

        def handler1(exc: Exception) -> HttpResponse:
            return HttpResponse("handler1")

        def handler2(exc: Exception) -> HttpResponse:
            return HttpResponse("handler2")

        GlobalErrorHandlerRegistry.register(ValueError, handler1)
        GlobalErrorHandlerRegistry.register(ValueError, handler2)

        result = GlobalErrorHandlerRegistry.get_handler(ValueError("test"))
        assert result is handler2

    def test_multiple_handlers_most_specific_wins(self) -> None:
        """Test that the most specific matching handler wins."""

        def base_handler(exc: Exception) -> HttpResponse:
            return HttpResponse("base")

        def specific_handler(exc: Exception) -> HttpResponse:
            return HttpResponse("specific")

        # Register base first, then specific
        GlobalErrorHandlerRegistry.register(Exception, base_handler)
        GlobalErrorHandlerRegistry.register(ValueError, specific_handler)

        # ValueError handler is more specific, so it wins
        result = GlobalErrorHandlerRegistry.get_handler(ValueError("test"))
        assert result is specific_handler


class TestPublicAPIFunctions:
    """Tests for public API functions."""

    def setup_method(self) -> None:
        """Clear handlers before each test."""
        clear_global_error_handlers()

    def teardown_method(self) -> None:
        """Clear handlers after each test."""
        clear_global_error_handlers()

    def test_register_global_error_handler(self) -> None:
        """Test the public register function."""

        def handler(exc: Exception) -> HttpResponse:
            return HttpResponse("handled")

        register_global_error_handler(ValueError, handler)
        result = GlobalErrorHandlerRegistry.get_handler(ValueError("test"))
        assert result is handler

    def test_clear_global_error_handlers(self) -> None:
        """Test the public clear function."""

        def handler(exc: Exception) -> HttpResponse:
            return HttpResponse("handled")

        register_global_error_handler(ValueError, handler)
        assert len(GlobalErrorHandlerRegistry._handlers) > 0

        clear_global_error_handlers()
        assert len(GlobalErrorHandlerRegistry._handlers) == 0
