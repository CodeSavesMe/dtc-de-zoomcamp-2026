# docker-ingestion-pipeline/ports/validator.py
from __future__ import annotations

from typing import Any, Protocol


class Validator(Protocol):
    """Validation port used by the core pipeline."""

    def infer_expected_month_from_table(self, table_name: str) -> str | None: ...
    def validate_staging(
        self, staging_table: str, expected_month: str | None = None
    ) -> dict[str, Any]: ...
