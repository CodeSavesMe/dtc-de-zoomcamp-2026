# docker_ingestion_pipeline/ports/schema.py
from __future__ import annotations

from typing import Protocol


class SchemaManager(Protocol):
    """Schema management port used by the core ingestion pipeline."""

    def ensure_final_schema(self, file_path: str, final_table: str) -> None: ...
    def recreate_staging_like_final(self, final_table: str, staging_table: str) -> None: ...
