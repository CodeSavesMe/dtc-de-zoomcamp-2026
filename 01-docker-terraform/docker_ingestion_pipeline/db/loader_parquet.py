# docker_ingestion_pipeline/db/loader_parquet.py
from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, ClassVar

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from loguru import logger

from docker_ingestion_pipeline.ports.database import CopyCapableDatabase
from docker_ingestion_pipeline.ports.loader import Loader
from docker_ingestion_pipeline.utils.datetime_fix import fix_datetime_columns
from docker_ingestion_pipeline.utils.identifiers import qident, sanitize_ident
from docker_ingestion_pipeline.utils.progress import progress_enable, track


@dataclass(frozen=True)
class ParquetStreamLoader(Loader):
    """
    Parquet loader using PostgreSQL COPY FROM STDIN with streaming.

    Strategy:
    - Iterate Parquet batches (pyarrow) to avoid loading the entire file into memory.
    - Convert each batch to pandas DataFrame for type coercion/cleanup.
    - Stream cleaned data into Postgres via COPY using an in-memory CSV buffer.
    """

    db: CopyCapableDatabase
    chunk_size: int = 100_000  # rows per arrow batch
    batch_size: int = 10_000  # rows per COPY batch within a chunk

    _COPY_DELIMITER: ClassVar[str] = ","

    _INT_TYPES: ClassVar[frozenset[str]] = frozenset({"bigint", "integer", "smallint"})
    _NUM_TYPES: ClassVar[frozenset[str]] = frozenset(
        {"numeric", "decimal", "real", "double precision"}
    )

    # -----------------------------
    # Metadata / preparation helpers
    # -----------------------------
    def _get_target_columns(self, table_name: str) -> list[str]:
        cols = self.db.get_table_columns(table_name)
        if not cols:
            raise RuntimeError(f"Target table {table_name} has no columns.")
        return cols

    def _get_pg_column_types(self, table_name: str, target_cols: list[str]) -> dict[str, str]:
        pg_types = dict(self.db.get_table_column_types(table_name))
        if not pg_types:
            raise RuntimeError(f"Could not read column types for table '{table_name}'")

        missing = [c for c in target_cols if c not in pg_types]
        if missing:
            raise RuntimeError(f"Missing type metadata for columns in '{table_name}': {missing}")

        return pg_types

    def _categorize_columns(
        self, target_cols: list[str], pg_types: dict[str, str]
    ) -> tuple[list[str], list[str]]:
        target_set = set(target_cols)
        int_cols = [c for c, t in pg_types.items() if t in self._INT_TYPES and c in target_set]
        num_cols = [c for c, t in pg_types.items() if t in self._NUM_TYPES and c in target_set]
        return int_cols, num_cols

    def _build_copy_sql(self, table_name: str, target_cols: list[str]) -> str:
        col_list_sql = ", ".join(qident(c) for c in target_cols)
        return (
            f"COPY {qident(table_name)} ({col_list_sql}) "
            f"FROM STDIN WITH (FORMAT csv, HEADER false, NULL '', DELIMITER '{self._COPY_DELIMITER}')"
        )

    # -----------------------------
    # Data coercion helpers
    # -----------------------------
    def _coerce_numeric_columns(self, df: pd.DataFrame, num_cols: list[str]) -> pd.DataFrame:
        """Force conversion to numeric; invalid entries become NaN (-> NULL)."""
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def _coerce_integer_columns(self, df: pd.DataFrame, int_cols: list[str]) -> pd.DataFrame:
        """
        Clean integer columns:
        - parse to numeric
        - if fractional values exist (e.g. 1.5), set to NULL to avoid COPY errors
        - convert to pandas nullable Int64
        """
        for col in int_cols:
            if col not in df.columns:
                continue

            series = pd.to_numeric(df[col], errors="coerce")

            frac = (series % 1).abs()
            has_decimals = series.notna() & (~np.isclose(frac, 0.0, atol=1e-9))
            if has_decimals.any():
                example = series[has_decimals].iloc[0]
                logger.warning(
                    f"Non-integer values found in integer column '{col}'. "
                    f"Setting to NULL. Example={example}"
                )
                series = series.mask(has_decimals, np.nan)

            df[col] = series.astype("Int64")

        return df

    # -----------------------------
    # COPY helpers
    # -----------------------------
    def _iter_copy_batches(self, df: pd.DataFrame) -> Iterable[pd.DataFrame]:
        rows = len(df)
        for start in range(0, rows, self.batch_size):
            yield df.iloc[start : start + self.batch_size]

    def _copy_batch(self, cursor: Any, copy_sql: str, batch: pd.DataFrame) -> int:
        buf = io.StringIO()
        batch.to_csv(
            buf,
            index=False,
            header=False,
            na_rep="",
            lineterminator="\n",
            quoting=csv.QUOTE_MINIMAL,
            doublequote=True,
        )
        buf.seek(0)
        cursor.copy_expert(copy_sql, buf)
        return len(batch)

    # -----------------------------
    # Public API
    # -----------------------------
    def load(self, file_path: str, table_name: str) -> None:
        """
        Stream Parquet -> transform -> COPY into Postgres.

        Notes:
        - This loader assumes the target table already exists with the desired schema.
        - It enforces column ordering based on DB metadata (source of truth).
        """
        table_name = sanitize_ident(table_name)

        target_cols = self._get_target_columns(table_name)
        pg_types = self._get_pg_column_types(table_name, target_cols)
        int_cols, num_cols = self._categorize_columns(target_cols, pg_types)

        copy_sql = self._build_copy_sql(table_name, target_cols)

        logger.info(f"Starting COPY (Parquet stream) into <green>{table_name}</green> ...")

        pf = pq.ParquetFile(file_path)
        total_rows_est = pf.metadata.num_rows if pf.metadata else None

        raw_conn = self.db.raw_connection()
        try:
            with raw_conn.cursor() as cur:
                total_rows = 0

                with track(total=total_rows_est, desc=f"Loading {table_name}") as tracker:
                    for batch_index, record_batch in enumerate(
                        pf.iter_batches(batch_size=self.chunk_size)
                    ):
                        # Convert to Arrow Table for column selection
                        arrow_table = pa.Table.from_batches([record_batch])

                        # First batch validation: ensure required columns exist
                        if batch_index == 0:
                            existing = set(arrow_table.column_names)
                            missing = [c for c in target_cols if c not in existing]
                            if missing:
                                raise RuntimeError(
                                    f"Parquet file missing required columns: {missing}"
                                )

                        # Select target columns in correct order, then convert to pandas
                        arrow_table = arrow_table.select(target_cols)
                        df = arrow_table.to_pandas(integer_object_nulls=True)

                        # Transformations / coercions
                        df = fix_datetime_columns(df)
                        df = self._coerce_numeric_columns(df, num_cols)
                        df = self._coerce_integer_columns(df, int_cols)
                        df = df.reindex(columns=target_cols)

                        # COPY in smaller batches
                        for out_batch in self._iter_copy_batches(df):
                            loaded = self._copy_batch(cur, copy_sql, out_batch)
                            total_rows += loaded
                            tracker.update(loaded)

                        if (batch_index + 1) % 5 == 0 and not progress_enable():
                            logger.info(
                                f"Processed {batch_index + 1} parquet chunks... Total rows: {total_rows}"
                            )

            raw_conn.commit()
            logger.success(f"Parquet Load Completed: {table_name} ({total_rows} rows)")

        except Exception:
            raw_conn.rollback()
            logger.exception("Failed to load Parquet data, transaction rolled back.")
            raise

        finally:
            raw_conn.close()
