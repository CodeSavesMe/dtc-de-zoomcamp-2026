# docker_ingestion_pipeline/utils/progress.py

from __future__ import annotations

import math
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

try:
    from tqdm import tqdm  # type: ignore
except ImportError:  # pragma: no cover
    tqdm = None

from docker_ingestion_pipeline.config import env_bool_os


def progress_enable() -> bool:
    """
    Check if progress bars are enabled via ENABLE_PROGRESS.

    Uses config.env_bool_os wrapper so callers don't need to pass os.environ.
    Defaults to True if missing.
    """
    return env_bool_os("ENABLE_PROGRESS", default=True)


def ceil_divide(total_items: int, items_per_batch: int) -> int:
    """Ceiling division helper for batching math."""
    if items_per_batch <= 0:
        raise ValueError("items_per_batch must be positive")
    return int(math.ceil(total_items / items_per_batch))


@dataclass
class NoopProgress:
    """No-op progress bar replacement when tqdm is disabled/unavailable."""

    def update(self, n: int) -> None:
        return


@contextmanager
def track(*, total: int | None, desc: str) -> Iterator[object]:
    """
    Unified progress context manager.

    - If ENABLE_PROGRESS=false OR tqdm not installed -> yields NoopProgress()
    - Otherwise -> yields a tqdm progress bar
    """
    if (not progress_enable()) or (tqdm is None):
        yield NoopProgress()
        return

    bar = tqdm(total=total, desc=desc, leave=False, dynamic_ncols=True)
    try:
        yield bar
    finally:
        bar.close()
