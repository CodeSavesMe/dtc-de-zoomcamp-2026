# docker_ingestion_pipeline/db/swapper.py
from __future__ import annotations

from dataclasses import dataclass

from loguru import logger
from sqlalchemy import text

from docker_ingestion_pipeline.db.client import PostgresClient
from docker_ingestion_pipeline.ports.swapper import Swapper
from docker_ingestion_pipeline.utils.identifiers import qident, sanitize_ident


@dataclass(frozen=True)
class AtomicSwapper(Swapper):
    """
    Atomic table swapper for PostgreSQL (infrastructure adapter).

    Algorithm (transactional):
    1) Drop any leftover backup table
    2) If final exists: rename final -> backup
    3) Rename staging -> final
    4) Drop backup (only after staging successfully becomes final)

    Notes:
    - Uses to_regclass() to check existence safely.
    - Uses a single transaction so partial swaps never persist.
    """

    db: PostgresClient

    def _schema(self) -> str:
        return sanitize_ident(getattr(self.db, "schema", "public"))

    def _fq(self, table: str) -> str:
        """Fully qualified table name: <schema>.<table> with safe quoting."""
        schema = self._schema()
        table = sanitize_ident(table)
        return f"{qident(schema)}.{qident(table)}"

    def _regclass(self, table: str) -> str:
        """
        Unquoted regclass text used by to_regclass(), e.g. schema.table
        We sanitize schema/table to avoid unexpected characters.
        """
        schema = self._schema()
        table = sanitize_ident(table)
        return f"{schema}.{table}"

    def _assert_table_exists(self, conn, table: str, *, label: str) -> None:
        """Fail fast with a clearer message than a raw SQL error."""
        exists = conn.execute(
            text("SELECT to_regclass(:t) IS NOT NULL"),
            {"t": self._regclass(table)},
        ).scalar_one()
        if not exists:
            raise RuntimeError(
                f"{label} table does not exist: {self._schema()}.{sanitize_ident(table)}"
            )

    def swap_tables_atomically(self, final_table: str, staging_table: str) -> None:
        final_table = sanitize_ident(final_table)
        staging_table = sanitize_ident(staging_table)
        backup_table = sanitize_ident(f"{final_table}__backup")

        schema = self._schema()
        fq_final = self._fq(final_table)
        fq_staging = self._fq(staging_table)
        fq_backup = self._fq(backup_table)

        logger.info(
            f"Swapping atomically (schema={schema}): "
            f"staging=<green>{staging_table}</green> -> final=<green>{final_table}</green>"
        )

        with self.db.begin() as conn:
            # Ensure staging exists up-front (better error than ALTER TABLE failure).
            self._assert_table_exists(conn, staging_table, label="Staging")

            # Cleanup any previous backup table (best practice for retries).
            conn.execute(text(f"DROP TABLE IF EXISTS {fq_backup}"))

            # If final exists, rename it to backup.
            final_exists = conn.execute(
                text("SELECT to_regclass(:t) IS NOT NULL"),
                {"t": self._regclass(final_table)},
            ).scalar_one()

            if final_exists:
                # Rename final -> backup (stays in same schema)
                conn.execute(text(f"ALTER TABLE {fq_final} RENAME TO {qident(backup_table)}"))

            # Rename staging -> final (stays in same schema)
            conn.execute(text(f"ALTER TABLE {fq_staging} RENAME TO {qident(final_table)}"))

            # Drop backup after successful swap
            conn.execute(text(f"DROP TABLE IF EXISTS {fq_backup}"))

        logger.success(f"Swap completed: <green>{schema}.{final_table}</green> updated")
