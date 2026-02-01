# docker_ingestion_pipeline/db/schema.py
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from loguru import logger
from sqlalchemy import text

from docker_ingestion_pipeline.db.client import PostgresClient
from docker_ingestion_pipeline.ports.schema import SchemaManager
from docker_ingestion_pipeline.utils.datetime_fix import fix_datetime_columns
from docker_ingestion_pipeline.utils.file_types import FileFormat, detect_file_format
from docker_ingestion_pipeline.utils.identifiers import qident, sanitize_ident


@dataclass(frozen=True)
class PostgresSchemaManager(SchemaManager):
    """
    PostgreSQL schema manager (infrastructure adapter).

    Responsibilities:
    - Infer a target schema from source files (CSV/TSV sampling, Parquet footer)
    - Create final table if missing
    - Recreate staging table LIKE final

    Note:
    - This adapter is allowed to use SQLAlchemy (engine/DDL), because it is not part
      of the core use-case layer.
    """

    db: PostgresClient
    sample_rows: int = 2000

    # ------------------------------------------------------------------
    # Public API (SchemaManager port)
    # ------------------------------------------------------------------
    def ensure_final_schema(self, file_path: str, final_table: str) -> None:
        """
        Ensure the final table exists with the correct schema inferred from the input file.

        Strategy:
        - Parquet: use footer schema (fast + accurate)
        - CSV/TSV: infer from a sample of rows using the correct delimiter
        """
        final_table = sanitize_ident(final_table)

        fmt = detect_file_format(file_path)

        if fmt == FileFormat.PARQUET:
            self._bootstrap_final_schema_from_parquet_footer(file_path, final_table)
            return

        if fmt in (FileFormat.CSV, FileFormat.TSV):
            self._bootstrap_final_schema_from_csv_sample(
                file_path=file_path,
                final_table=final_table,
                sample_rows=self.sample_rows,
                fmt=fmt,
            )
            return

        raise ValueError(f"Unsupported file format for schema bootstrap: {file_path} ({fmt})")

    def recreate_staging_like_final(self, final_table: str, staging_table: str) -> None:
        """
        Drop staging if it exists, then create a new empty staging table
        mirroring the structure of the final table.
        """
        final_table = sanitize_ident(final_table)
        staging_table = sanitize_ident(staging_table)

        # Use one transaction so we never end up with partial staging state.
        with self.db.begin() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {qident(staging_table)}"))
            conn.execute(
                text(
                    f"CREATE TABLE {qident(staging_table)} "
                    f"(LIKE {qident(final_table)} INCLUDING ALL)"
                )
            )

        logger.info(
            f"Created staging <green>{staging_table}</green> LIKE <green>{final_table}</green>"
        )

    # ------------------------------------------------------------------
    # CSV/TSV bootstrap
    # ------------------------------------------------------------------
    def _bootstrap_final_schema_from_csv_sample(
        self,
        file_path: str,
        final_table: str,
        sample_rows: int,
        fmt: FileFormat = FileFormat.CSV,
    ) -> None:
        """
        Infer schema from a CSV/TSV sample and create the final table.

        Critical detail:
        - TSV must use '\\t' separator; otherwise pandas reads everything as one column.
        """
        separator = "\t" if fmt == FileFormat.TSV else ","

        logger.info(
            f"Bootstrapping schema for <green>{final_table}</green> from {fmt.name} sample rows={sample_rows}"
        )

        df = pd.read_csv(
            file_path,
            nrows=sample_rows,
            compression="infer",
            low_memory=False,
            sep=separator,
        )

        # Normalize datetimes to reduce downstream surprises.
        df = fix_datetime_columns(df)

        # Create an empty table with the inferred columns/types.
        # We intentionally use df.head(0) so no data is inserted.
        #
        # This is adapter-level code: it can depend on SQLAlchemy engine.
        df.head(0).to_sql(
            name=final_table,
            con=self.db.engine,
            if_exists="replace",
            index=False,
        )

        logger.info(f"Schema bootstrapped for <green>{final_table}</green>")

    # ------------------------------------------------------------------
    # Parquet bootstrap
    # ------------------------------------------------------------------
    def _arrow_type_to_pg(self, arrow_type: pa.DataType) -> str:
        """
        Map PyArrow data types to PostgreSQL column types.

        This is a pragmatic mapping for NYC TLC datasets; unknown types fall back to TEXT.
        """
        if pa.types.is_timestamp(arrow_type):
            if getattr(arrow_type, "tz", None):
                return "TIMESTAMPTZ"
            return "TIMESTAMP"

        if pa.types.is_int8(arrow_type) or pa.types.is_int16(arrow_type):
            return "SMALLINT"
        if pa.types.is_int32(arrow_type):
            return "INTEGER"
        if pa.types.is_int64(arrow_type):
            return "BIGINT"

        if pa.types.is_float32(arrow_type):
            return "REAL"
        if pa.types.is_float64(arrow_type):
            return "DOUBLE PRECISION"

        if pa.types.is_boolean(arrow_type):
            return "BOOLEAN"

        if pa.types.is_string(arrow_type) or pa.types.is_large_string(arrow_type):
            return "TEXT"

        if pa.types.is_date32(arrow_type) or pa.types.is_date64(arrow_type):
            return "DATE"

        if pa.types.is_decimal(arrow_type):
            return f"NUMERIC({arrow_type.precision},{arrow_type.scale})"

        if pa.types.is_binary(arrow_type) or pa.types.is_large_binary(arrow_type):
            return "BYTEA"

        logger.debug(f"Arrow type fallback to TEXT: {arrow_type}")
        return "TEXT"

    def _bootstrap_final_schema_from_parquet_footer(self, file_path: str, final_table: str) -> None:
        """
        Create final table schema by reading the Parquet footer.

        Benefits:
        - No sampling needed
        - More accurate than dtype inference from a subset of rows
        """
        logger.info(f"Bootstrapping schema for <green>{final_table}</green> from Parquet footer")

        pf = pq.ParquetFile(file_path)
        schema = pf.schema_arrow

        cols_sql: list[str] = []
        for field in schema:
            col = sanitize_ident(field.name)
            pg_type = self._arrow_type_to_pg(field.type)
            cols_sql.append(f"{qident(col)} {pg_type}")

        ddl = f"CREATE TABLE {qident(final_table)} ({', '.join(cols_sql)})"

        with self.db.begin() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {qident(final_table)}"))
            conn.execute(text(ddl))

        logger.info(f"Schema bootstrapped for <green>{final_table}</green>")
