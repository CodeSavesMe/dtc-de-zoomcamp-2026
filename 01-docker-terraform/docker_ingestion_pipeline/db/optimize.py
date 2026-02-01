# docker_ingestion_pipeline/db/optimize.py
from __future__ import annotations

from dataclasses import dataclass

from loguru import logger
from sqlalchemy import text

from docker_ingestion_pipeline.db.client import PostgresClient
from docker_ingestion_pipeline.ports.optimize import Optimizer
from docker_ingestion_pipeline.utils.identifiers import qident, sanitize_ident


@dataclass(frozen=True)
class PostLoadOptimizer(Optimizer):
    """
    Post-load optimizer for PostgreSQL (infrastructure adapter).

    Currently:
    - Runs ANALYZE to refresh planner statistics after large loads.
    """

    db: PostgresClient

    def _schema(self) -> str:
        return sanitize_ident(getattr(self.db, "schema", "public"))

    def _fq(self, table: str) -> str:
        """Fully qualified table name: <schema>.<table> with safe quoting."""
        schema = self._schema()
        table = sanitize_ident(table)
        return f"{qident(schema)}.{qident(table)}"

    def analyze(self, table_name: str) -> None:
        table_name = sanitize_ident(table_name)
        fq_table = self._fq(table_name)

        with self.db.begin() as conn:
            conn.execute(text(f"ANALYZE {fq_table}"))

        logger.info(f"ANALYZE completed for <green>{self._schema()}.{table_name}</green>")
