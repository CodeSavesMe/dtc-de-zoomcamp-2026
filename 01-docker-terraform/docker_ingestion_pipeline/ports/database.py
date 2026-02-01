# docker_ingestion_pipeline/ports/database.py
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class Database(Protocol):
    """
    Library-agnostic database port (DIP-friendly).

    Core (use-cases) should depend on this interface, NOT on SQLAlchemy types.
    Concrete implementations (adapters) may use SQLAlchemy/psycopg internally.
    """

    schema: str

    # --- Existence / metadata ---
    def table_exists(self, table_name: str) -> bool: ...
    def get_table_columns(self, table_name: str) -> list[str]: ...
    def get_table_column_types(self, table_name: str) -> Mapping[str, str]: ...

    # --- Data movement helpers required by the core pipeline ---
    def drop_table_if_exists(self, table_name: str) -> None: ...
    def append_from_staging(self, final_table: str, staging_table: str) -> int: ...


class CopyCapableDatabase(Database, Protocol):
    """
    Optional port for loaders that need COPY or raw driver access.

    Why separate:
    - Not all Database implementations need to support COPY.
    - Keeps the core Database interface small (ISP).
    """

    def raw_connection(self) -> Any: ...
