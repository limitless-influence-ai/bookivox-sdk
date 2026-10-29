"""Exception hierarchy for the Bookivox SDK."""

from __future__ import annotations

from typing import Any


class BookivoxError(Exception):
    """Base class for every error raised by the Bookivox SDK."""


class APIConnectionError(BookivoxError):
    """The API could not be reached (DNS, TLS, connection reset, ...)."""


class APITimeoutError(APIConnectionError):
    """The request timed out before a response was received."""


class APIStatusError(BookivoxError):
    """The API answered with a non-2xx status code."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        request_id: str | None = None,
        body: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        # Correlation id echoed by the API (``X-Request-ID``), safe to log.
        self.request_id = request_id
        self.body = body


class BadRequestError(APIStatusError):
    """400 — the request was malformed."""


class AuthenticationError(APIStatusError):
    """401 — the API key is missing, invalid or revoked."""


class PermissionDeniedError(APIStatusError):
    """403 — the API key is valid but not allowed to perform this action."""


class NotFoundError(APIStatusError):
    """404 — the resource does not exist (or is not visible to this organization)."""


class ConflictError(APIStatusError):
    """409 — the request conflicts with the current state of the resource."""


class ValidationError(APIStatusError):
    """422 — the payload failed server-side validation."""


class RateLimitError(APIStatusError):
    """429 — too many requests. ``retry_after`` is expressed in seconds."""

    def __init__(self, message: str, *, retry_after: float | None = None, **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class ServerError(APIStatusError):
    """5xx — the API failed to process the request."""


_STATUS_ERRORS: dict[int, type[APIStatusError]] = {
    400: BadRequestError,
    401: AuthenticationError,
    403: PermissionDeniedError,
    404: NotFoundError,
    409: ConflictError,
    422: ValidationError,
    429: RateLimitError,
}


def error_for_status(
    status_code: int,
    *,
    message: str,
    request_id: str | None = None,
    body: Any = None,
    retry_after: float | None = None,
) -> APIStatusError:
    """Map an HTTP status code to the most specific exception class."""
    error_cls = _STATUS_ERRORS.get(status_code)
    if error_cls is None:
        error_cls = ServerError if status_code >= 500 else APIStatusError
    if error_cls is RateLimitError:
        return RateLimitError(
            message,
            retry_after=retry_after,
            status_code=status_code,
            request_id=request_id,
            body=body,
        )
    return error_cls(message, status_code=status_code, request_id=request_id, body=body)
