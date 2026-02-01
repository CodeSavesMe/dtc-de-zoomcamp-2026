# docker_ingestion_pipeline/ports/loader.py
from __future__ import annotations

from typing import Protocol


class Loader(Protocol):
    """
    Loader port.

    Implementations load data from a local file into a target table.
    The core pipeline uses this interface without knowing file format details.
    """

    def load(self, file_path: str, table_name: str) -> None: ...
