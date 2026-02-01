# docker_ingestion_pipeline/db/lock.py
from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from loguru import logger
from sqlalchemy import text

from docker_ingestion_pipeline.db.client import PostgresClient
from docker_ingestion_pipeline.ports.lock import LockManager


@dataclass(frozen=True)
class AdvisoryLock(LockManager):
    """
    PostgreSQL advisory lock manager (infrastructure adapter).

    Key properties:
    - Uses session-scoped advisory locks: the lock is tied to the connection.
    - Keeps the connection open while the lock is held to prevent accidental release.
    - Polls using pg_try_advisory_lock to avoid blocking indefinitely.
    """

    db: PostgresClient

    _LOCK_SQL = text("SELECT pg_try_advisory_lock(hashtext(:k)::bigint)")
    _UNLOCK_SQL = text("SELECT pg_advisory_unlock(hashtext(:k)::bigint)")

    @contextmanager
    def acquire(
        self, lock_key: str, *, timeout_s: float | None = 60.0, poll_s: float = 0.2
    ) -> Iterator[None]:
        """
        Acquire an advisory lock, polling until success or timeout.

        Args:
            lock_key:
              A logical lock identifier (e.g. "ingest:public:yellow_tripdata_2024_01").

            timeout_s:
              Max time to wait. If None, wait indefinitely.

            poll_s:
              Poll interval (seconds) between lock attempts.
        """
        if poll_s <= 0:
            raise ValueError("poll_s must be > 0")

        # IMPORTANT: keep a single connection open while the lock is held.
        with self.db.connect() as conn:
            start = time.monotonic()

            while True:
                acquired = bool(conn.execute(self._LOCK_SQL, {"k": lock_key}).scalar_one())

                if acquired:
                    logger.info(f"Advisory lock acquired: {lock_key}")
                    break

                if timeout_s is not None and (time.monotonic() - start) >= timeout_s:
                    raise TimeoutError(f"Failed to acquire lock '{lock_key}' after {timeout_s}s")

                time.sleep(poll_s)

            try:
                yield
            finally:
                # Always release with the same connection (session-scoped lock).
                try:
                    conn.execute(self._UNLOCK_SQL, {"k": lock_key})
                    logger.info(f"Advisory lock released: {lock_key}")
                except Exception as e:
                    # Best-effort unlock: if connection drops, PG will release lock anyway.
                    logger.warning(f"Failed to release lock '{lock_key}': {e}")
