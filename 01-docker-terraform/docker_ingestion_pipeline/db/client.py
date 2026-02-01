# docker_ingestion_pipeline/db/client.py
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ContextManager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Connection, Engine

from docker_ingestion_pipeline.utils.identifiers import qident, sanitize_ident


@dataclass(frozen=True)
class PostgresClient:
    """
    Small wrapper around a SQLAlchemy Postgres engine (adapter layer).

    Design goals:
    - Keep schema handling consistent (search_path + explicit schema checks).
    - Provide DB capabilities required by the core pipeline.
    - Allow raw connections for COPY-based loaders.
    """

    engine: Engine
    schema: str = "public"

    @classmethod
    def from_params(
        cls,
        user: str,
        password: str,
        host: str,
        port: int,
        db: str,
        schema: str = "public",
    ) -> PostgresClient:
        schema = schema.strip()
        if not schema:
            raise ValueError("schema must be a non-empty string")

        url = URL.create(
            drivername="postgresql+psycopg2",
            username=user,
            password=password,
            host=host,
            port=port,
            database=db,
        )

        engine = create_engine(
            url,
            pool_pre_ping=True,
            future=True,
            connect_args={
                # Ensure every connection uses the target schema by default.
                "options": f"-csearch_path={schema},public"
            },
        )

        client = cls(engine=engine, schema=schema)
        client.ensure_schema_exists()
        return client

    # ---------------------------------------------------------------------
    # Small internal helpers
    # ---------------------------------------------------------------------
    def _schema(self) -> str:
        return sanitize_ident(self.schema)

    def _fq(self, table_name: str) -> str:
        """Fully qualified table reference: <schema>.<table>."""
        schema = self._schema()
        table = sanitize_ident(table_name)
        return f"{qident(schema)}.{qident(table)}"

    # ---------------------------------------------------------------------
    # Schema lifecycle
    # ---------------------------------------------------------------------
    def ensure_schema_exists(self) -> None:
        """Create schema if it does not exist."""
        schema = self._schema()
        with self.engine.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {qident(schema)}"))

    # ---------------------------------------------------------------------
    # Minimal DB operations used by the core pipeline
    # ---------------------------------------------------------------------
    def table_exists(self, table_name: str) -> bool:
        """Check whether a table exists in the configured schema."""
        table_name = sanitize_ident(table_name)
        with self.engine.connect() as conn:
            return bool(
                conn.execute(
                    text(
                        """
                        SELECT EXISTS (
                            SELECT 1
                            FROM information_schema.tables
                            WHERE table_schema = :s
                              AND table_name   = :t
                        )
                        """
                    ),
                    {"s": self.schema, "t": table_name},
                ).scalar_one()
            )

    def drop_table_if_exists(self, table_name: str) -> None:
        """
        Drop a table if it exists (fully-qualified).

        Used by the core pipeline for best-effort cleanup.
        """
        fq = self._fq(table_name)
        with self.engine.begin() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {fq}"))

    def append_from_staging(self, final_table: str, staging_table: str) -> int:
        """
        Insert all rows from staging into final table.

        Returns:
        - rowcount when available; otherwise -1 (depends on DBAPI behavior).
        """
        fq_final = self._fq(final_table)
        fq_staging = self._fq(staging_table)

        with self.engine.begin() as conn:
            result = conn.execute(text(f"INSERT INTO {fq_final} SELECT * FROM {fq_staging}"))
            return int(getattr(result, "rowcount", -1))

    # ---------------------------------------------------------------------
    # Metadata helpers (used by schema manager / loaders)
    # ---------------------------------------------------------------------
    def get_table_columns(self, table_name: str) -> list[str]:
        """Return column names in database order."""
        table_name = sanitize_ident(table_name)
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = :s
                      AND table_name   = :t
                    ORDER BY ordinal_position
                    """
                ),
                {"s": self.schema, "t": table_name},
            ).fetchall()
        return [r[0] for r in rows]

    def get_table_column_types(self, table_name: str) -> dict[str, str]:
        """Return column data types from information_schema."""
        table_name = sanitize_ident(table_name)
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = :s
                      AND table_name   = :t
                    ORDER BY ordinal_position
                    """
                ),
                {"s": self.schema, "t": table_name},
            ).fetchall()
        return {col: dtype for col, dtype in rows}

    # ---------------------------------------------------------------------
    # Low-level access (infrastructure convenience)
    # ---------------------------------------------------------------------
    def raw_connection(self) -> Any:
        """Return a psycopg2 connection (used by COPY)."""
        return self.engine.raw_connection()

    def begin(self) -> ContextManager[Connection]:
        """Transaction context manager."""
        return self.engine.begin()

    def connect(self) -> ContextManager[Connection]:
        """Connection context manager."""
        return self.engine.connect()

    # ---------------------------------------------------------------------
    # Optional: generic SQL execution helper
    # ---------------------------------------------------------------------
    def execute_sql(self, sql: str, params: Mapping[str, Any] | None = None) -> Any:
        """
        Execute raw SQL with a short-lived connection.

        Accepts plain SQL strings to avoid leaking SQLAlchemy objects upward.
        """
        with self.engine.connect() as conn:
            return conn.execute(text(sql), params or {})
