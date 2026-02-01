# docker-ingestion-pipeline/ports/swapper.py
from __future__ import annotations

from typing import Protocol


class Swapper(Protocol):
    """Atomic swap port used by the core pipeline."""

    def swap_tables_atomically(self, final_table: str, staging_table: str) -> None: ...
