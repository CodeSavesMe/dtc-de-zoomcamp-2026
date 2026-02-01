# docker_ingestion_pipeline/ports/optimize.py

from __future__ import annotations

from typing import Protocol


class Optimizer(Protocol):
    """Post-load maintenance interface."""

    def analyze(self, table_name: str) -> None: ...
