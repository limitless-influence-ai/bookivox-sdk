"""Synchronous Bookivox API client.

The typed resource methods live in ``_generated.py`` (auto-generated from the
OpenAPI schema). This module owns everything the generator cannot express:
authentication, transport, retries, timeouts and error mapping.
"""

from __future__ import annotations

import os
import random
import time
from typing import Any, Mapping

import httpx

from ._generated import GeneratedMethods
from .errors import APIConnectionError, APITimeoutError, error_for_status

DEFAULT_BASE_URL = "https://api.bookivox.com"
ENV_API_KEY = "BOOKIVOX_API_KEY"

# Idempotent verbs only: replaying a POST could create duplicates or bill twice.
RETRYABLE_METHODS = frozenset({"GET", "HEAD", "PUT", "DELETE", "OPTIONS"})
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
MAX_RETRY_AFTER = 30.0


def _error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, Mapping):
        detail = payload.get("detail") or payload.get("message") or payload.get("error")
        if isinstance(detail, str) and detail:
            return detail
        if detail is not None:
            return str(detail)
    text = response.text.strip()
    return text[:500] if text else f"HTTP {response.status_code}"


def _retry_after(response: httpx.Response) -> float | None:
    raw = response.headers.get("retry-after")
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        return None


class Bookivox(GeneratedMethods):
    """Client for the Bookivox public API.

    Args:
        api_key: Organization API key (``bookeys_sk-...``). Falls back to the
            ``BOOKIVOX_API_KEY`` environment variable.
        timeout: Per-request timeout in seconds.
        max_retries: Number of retries for idempotent requests failing with a
            transient error (429/5xx/network).
        http_client: Optional pre-configured ``httpx.Client`` (proxy, transport,
            instrumentation). Ownership stays with the caller in that case.

    The API key is only ever sent in the ``X-API-Key`` header; it is never put
    in a URL, logged, or included in exceptions.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        timeout: float = 30.0,
        max_retries: int = 2,
        http_client: httpx.Client | None = None,
    ) -> None:
        resolved_key = api_key or os.environ.get(ENV_API_KEY)
        if not resolved_key:
            raise ValueError(
                f"Missing API key. Pass api_key=... or set {ENV_API_KEY}."
            )
        self._api_key = resolved_key
        self.base_url = DEFAULT_BASE_URL
        self.max_retries = max(0, max_retries)
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(
            timeout=httpx.Timeout(timeout),
            headers={
                "X-API-Key": resolved_key,
                "Accept": "application/json",
                "User-Agent": "bookivox-python-sdk",
            },
            follow_redirects=False,
        )

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        """Release the underlying HTTP connection pool."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "Bookivox":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # -- transport ---------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Any = None,
    ) -> Any:
        """Send a request and return the decoded JSON body (``None`` if empty)."""
        method = method.upper()
        clean_params = (
            {key: value for key, value in params.items() if value is not None}
            if params
            else None
        )
        headers = {"X-API-Key": self._api_key}
        if json_body is not None:
            headers["Content-Type"] = "application/json"

        attempt = 0
        while True:
            try:
                response = self._client.request(
                    method,
                    f"{self.base_url}{path}",
                    params=clean_params,
                    json=json_body,
                    headers=headers,
                )
            except httpx.TimeoutException as exc:
                if attempt < self.max_retries and method in RETRYABLE_METHODS:
                    self._sleep(attempt)
                    attempt += 1
                    continue
                raise APITimeoutError(f"Request to {path} timed out.") from exc
            except httpx.HTTPError as exc:
                if attempt < self.max_retries and method in RETRYABLE_METHODS:
                    self._sleep(attempt)
                    attempt += 1
                    continue
                raise APIConnectionError(f"Could not reach the Bookivox API: {exc}") from exc

            if response.status_code in RETRYABLE_STATUS and method in RETRYABLE_METHODS:
                if attempt < self.max_retries:
                    retry_after = _retry_after(response)
                    self._sleep(attempt, retry_after=retry_after)
                    attempt += 1
                    continue

            if response.status_code >= 400:
                raise error_for_status(
                    response.status_code,
                    message=_error_message(response),
                    request_id=response.headers.get("x-request-id"),
                    body=_safe_body(response),
                    retry_after=_retry_after(response),
                )

            if response.status_code == 204 or not response.content:
                return None
            if "application/json" not in response.headers.get("content-type", ""):
                return response.text
            return response.json()

    # -- helpers -----------------------------------------------------------

    def _sleep(self, attempt: int, *, retry_after: float | None = None) -> None:
        if retry_after is not None:
            time.sleep(min(retry_after, MAX_RETRY_AFTER))
            return
        # Exponential backoff with jitter to avoid thundering herds.
        delay = min(2.0 ** attempt, 8.0)
        time.sleep(delay * (0.5 + random.random() / 2))

    def __repr__(self) -> str:
        # Never leak the API key.
        return f"Bookivox(base_url={self.base_url!r})"


def _safe_body(response: httpx.Response) -> Any:
    """Best-effort decoded error body, capped to avoid logging huge payloads."""
    try:
        payload = response.json()
    except ValueError:
        return None
    if isinstance(payload, (dict, list)) and len(str(payload)) > 2000:
        return {"truncated": True}
    return payload
