"""Tiny JSON-over-HTTP helper with retries (stdlib only, so the Lambda needs no packaging)."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from typing import Any

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class HttpError(RuntimeError):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def get_bytes(
    url: str,
    params: Mapping[str, Any] | None = None,
    *,
    headers: Mapping[str, str] | None = None,
    timeout: float = 20.0,
    retries: int = 3,
    backoff: float = 1.5,
    max_bytes: int | None = None,
    opener: Callable[..., Any] = urllib.request.urlopen,
    sleep: Callable[[float], None] = time.sleep,
) -> bytes:
    """GET a URL and return the body, retrying transient failures with exponential backoff.

    `max_bytes` refuses a response larger than that (a guard against a feed that suddenly grows or
    is replaced by something huge); it is not retried.
    """
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url, headers={"User-Agent": "skills-radar/0.1", **(headers or {})}
    )
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with opener(request, timeout=timeout) as response:
                if max_bytes is None:
                    return response.read()
                body = response.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise HttpError(f"response larger than {max_bytes} bytes")
                return body
        except urllib.error.HTTPError as exc:
            if exc.code not in RETRYABLE_STATUS:
                raise HttpError(f"GET failed with HTTP {exc.code}", exc.code) from exc
            last_error = exc
        except urllib.error.URLError as exc:
            last_error = exc
        if attempt < retries:
            sleep(backoff * (2**attempt))
    status = last_error.code if isinstance(last_error, urllib.error.HTTPError) else None
    raise HttpError(f"GET failed after {retries + 1} attempts", status) from last_error


def get_json(
    url: str,
    params: Mapping[str, Any] | None = None,
    *,
    headers: Mapping[str, str] | None = None,
    timeout: float = 20.0,
    retries: int = 3,
    backoff: float = 1.5,
    opener: Callable[..., Any] = urllib.request.urlopen,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    """GET a URL and decode JSON, retrying transient failures with exponential backoff."""
    body = get_bytes(
        url,
        params,
        headers=headers,
        timeout=timeout,
        retries=retries,
        backoff=backoff,
        opener=opener,
        sleep=sleep,
    )
    return json.loads(body.decode("utf-8"))
