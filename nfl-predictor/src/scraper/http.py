"""Shared HTTP helper with retry + exponential backoff for scrapers.

All scrapers should fetch through ``get_with_retry`` so transient failures
(timeouts, dropped connections, 5xx, 429) are retried with backoff instead of
causing silent data gaps. Permanent errors (4xx other than 429) return the
response immediately so callers can handle them.
"""

import logging
import random
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

DEFAULT_RETRIES = 3
DEFAULT_BACKOFF = 1.0          # base seconds; doubled each attempt
RETRY_STATUS = frozenset({429, 500, 502, 503, 504})


def _retry_after(resp: "requests.Response") -> Optional[float]:
    """Parse a ``Retry-After`` header (seconds form) if present."""
    val = resp.headers.get("Retry-After")
    if not val:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def get_with_retry(
    url: str,
    *,
    retries: int = DEFAULT_RETRIES,
    backoff: float = DEFAULT_BACKOFF,
    timeout: float = 10.0,
    session: Optional["requests.Session"] = None,
    **kwargs,
) -> "requests.Response":
    """GET ``url`` with retries on transient errors.

    Retries on connection errors / timeouts and on retryable status codes
    (429, 5xx), using exponential backoff with jitter and honouring
    ``Retry-After`` when the server provides it. ``raise_for_status`` is NOT
    called — the caller decides what to do with the final response.

    Args:
        url:      Target URL.
        retries:  Total attempts (>=1).
        backoff:  Base backoff seconds (attempt N waits ~backoff * 2**(N-1)).
        timeout:  Per-request timeout in seconds.
        session:  Optional ``requests.Session`` (or any object with ``.get``);
                  falls back to module-level ``requests.get``.
        **kwargs: Passed through to the underlying ``get`` (params, headers, …).

    Returns:
        The final ``requests.Response``.

    Raises:
        requests.RequestException: if every attempt raised.
    """
    getter = session.get if session is not None else requests.get
    last_exc: Optional[BaseException] = None
    resp: Optional["requests.Response"] = None

    for attempt in range(1, max(1, retries) + 1):
        try:
            resp = getter(url, timeout=timeout, **kwargs)
            if resp.status_code in RETRY_STATUS and attempt < retries:
                wait = _retry_after(resp) or backoff * (2 ** (attempt - 1))
                logger.warning(
                    "GET %s -> HTTP %s (attempt %d/%d); retrying in %.1fs",
                    url, resp.status_code, attempt, retries, wait,
                )
                time.sleep(wait + random.uniform(0.0, 0.3))
                continue
            return resp
        except requests.RequestException as exc:
            last_exc = exc
            if attempt >= retries:
                break
            wait = backoff * (2 ** (attempt - 1))
            logger.warning(
                "GET %s failed (attempt %d/%d): %s; retrying in %.1fs",
                url, attempt, retries, exc, wait,
            )
            time.sleep(wait + random.uniform(0.0, 0.3))

    if last_exc is not None:
        raise last_exc
    return resp  # type: ignore[return-value]  # set on the final non-retryable path
