# docker_ingestion_pipeline/ports/lock.py
from __future__ import annotations

from typing import ContextManager, Protocol


class LockManager(Protocol):
    """
    Lock manager port.

    Implementations may provide advisory locks, distributed locks, etc.
    The context manager must keep the lock held for the duration of the context.
    """

    def acquire(
        self,
        lock_key: str,
        *,
        timeout_s: float | None = 60.0,
        poll_s: float = 0.2,
    ) -> ContextManager[None]: ...
