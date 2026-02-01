# docker_ingestion_pipeline/utils/file_types.py
from __future__ import annotations

from enum import Enum
from pathlib import Path


class FileFormat(str, Enum):
    """Supported input file formats."""

    CSV = "csv"
    TSV = "tsv"
    PARQUET = "parquet"
    UNKNOWN = "unknown"


def detect_file_format(path: str | Path) -> FileFormat:
    """
    Detect file format from filename/extension.

    Notes:
    - This is intentionally extension-based (fast and predictable).
    - Compression suffixes like .gz are supported for CSV/TSV.
    """
    p = str(path).lower()

    # Parquet
    if p.endswith(".parquet"):
        return FileFormat.PARQUET

    # CSV (plain or gz)
    if p.endswith(".csv") or p.endswith(".csv.gz"):
        return FileFormat.CSV

    # TSV (plain or gz)
    if p.endswith(".tsv") or p.endswith(".tsv.gz"):
        return FileFormat.TSV

    return FileFormat.UNKNOWN
