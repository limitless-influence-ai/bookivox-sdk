"""Bookivox Python SDK."""

from __future__ import annotations

from ._generated import GeneratedMethods
from .client import DEFAULT_BASE_URL, Bookivox
from .errors import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    BookivoxError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from .models import *  # noqa: F401,F403
from .models import __all__ as _model_exports

__version__ = "0.1.1"

__all__ = [
    "Bookivox",
    "GeneratedMethods",
    "DEFAULT_BASE_URL",
    "BookivoxError",
    "APIConnectionError",
    "APITimeoutError",
    "APIStatusError",
    "BadRequestError",
    "AuthenticationError",
    "PermissionDeniedError",
    "NotFoundError",
    "ConflictError",
    "ValidationError",
    "RateLimitError",
    "ServerError",
    *_model_exports,
]
