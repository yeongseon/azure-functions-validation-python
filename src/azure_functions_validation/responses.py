"""Handler response values and fixed request-validation error contracts."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True, kw_only=True)
class ResponseSpec(Generic[T]):
    """Return content through normal validation with per-return status and headers.

    Transport fields are checked by the pipeline, not during construction.
    A final None content takes precedence over status and produces 204.
    """

    content: T
    status_code: int | None = None
    headers: Mapping[str, str] | Sequence[tuple[str, str]] | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ErrorResponseSpec:
    """A synchronous formatter result, eligible only for request schema failures."""

    content: dict[str, Any]
    status_code: int | None = None
    media_type: str | None = None
    headers: Mapping[str, str] | Sequence[tuple[str, str]] | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidationErrorResponse:
    """Declare a fixed transport and optional Pydantic error-content contract."""

    status_code: int = 422
    media_type: str = "application/json"
    response_model: Any = None
