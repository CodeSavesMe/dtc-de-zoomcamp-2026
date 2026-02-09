# src/dw03/runtime/retry.py

from __future__ import annotations

import random
import time


def sleep_with_backoff(attempt: int, base_seconds: float = 1.0, max_seconds: float = 60.0) -> None:
    """
    Exponential backoff + jitter.
    attempt=1 -> ~1s
    attempt=2 -> ~2s
    attempt=3 -> ~4s
    ... capped by max_seconds
    """
    delay = min(max_seconds, base_seconds * (2 ** (attempt - 1)))
    delay *= random.uniform(0.5, 1.5)
    time.sleep(delay)


def should_retry_http_status(status_code: int) -> bool:
    """
    Retry only what usually makes sense:
    - 429 Too Many Requests
    - 5xx server errors
    """
    if status_code == 429:
        return True
    return 500 <= status_code <= 599
