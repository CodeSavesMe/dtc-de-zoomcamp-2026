# docker_ingestion_pipeline/db/loader_tsv.py
from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, ClassVar

import numpy as np
import pandas as pd
from loguru import logger

from docker_ingestion_pipeline.ports.database import CopyCapableDatabase
from docker_ingestion_pipeline.ports.loader import Loader
from docker_ingestion_pipeline.utils.datetime_fix import fix_datetime_columns
from docker_ingestion_pipeline.utils.identifiers import qident, sanitize_ident
from docker_ingestion_pipeline.utils.progress import progress_enable, track


@dataclass(frozen=True)
class TsvCopyLoader(Loader):
    """
    TSV loader using PostgreSQL COPY FROM STDIN.

    Strategy:
    - Read TSV input in Pandas chunks.
    - Convert to CSV lines in-memory (stable parsing for Postgres COPY).
    - Apply type-aware coercions (NUMERIC/INTEGER) to reduce COPY failures.
    """

    db: CopyCapableDatabase
    chunk_size: int = 100_000
    batch_size: int = 10_000
    encoding: str = "utf-8"

    # Input delimiter (TSV)
    delimiter: str = "\t"

    # COPY stream delimiter (we always stream as CSV for Postgres stability)
    _COPY_DELIMITER: ClassVar[str] = ","

    _INT_TYPES: ClassVar[frozenset[str]] = frozenset({"bigint", "integer", "smallint"})
    _NUM_TYPES: ClassVar[frozenset[str]] = frozenset(
        {"numeric", "decimal", "real", "double precision"}
    )

    # -----------------------------
    # Validation / preparation
    # -----------------------------
    def _validate_input_delimiter(self) -> None:
        """Ensure the TSV input delimiter is safe and predictable."""
        if not isinstance(self.delimiter, str) or len(self.delimiter) != 1:
            raise ValueError("TSV delimiter must be a single character.")
        if self.delimiter in {"\n", "\r", "'"}:
            raise ValueError("TSV delimiter contains unsafe character.")

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
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def _coerce_integer_columns(self, df: pd.DataFrame, int_cols: list[str]) -> pd.DataFrame:
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
    # COPY execution
    # -----------------------------
    def _iter_batches(self, df: pd.DataFrame) -> Iterable[pd.DataFrame]:
        rows = len(df)
        for start in range(0, rows, self.batch_size):
            yield df.iloc[start : start + self.batch_size]

    def _copy_batch(self, cursor: Any, copy_sql: str, batch: pd.DataFrame) -> int:
        """
        Convert a batch into CSV rows and stream into Postgres COPY.
        """
        buf = io.StringIO()
        batch.to_csv(
            buf,
            index=False,
            header=False,
            sep=self._COPY_DELIMITER,  # convert TSV -> CSV for COPY stream
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
        Load TSV file into target table using COPY.

        Steps:
        - read DB schema metadata
        - stream TSV chunks (pandas)
        - normalize/transform into DB column order
        - COPY batches into Postgres
        """
        self._validate_input_delimiter()

        table_name = sanitize_ident(table_name)

        target_cols = self._get_target_columns(table_name)
        pg_types = self._get_pg_column_types(table_name, target_cols)
        int_cols, num_cols = self._categorize_columns(target_cols, pg_types)

        copy_sql = self._build_copy_sql(table_name, target_cols)

        logger.info(f"Starting COPY (TSV chunks) into <green>{table_name}</green> ...")

        raw_conn = self.db.raw_connection()
        try:
            with raw_conn.cursor() as cur:
                total_rows = 0
                target_set = set(target_cols)

                with track(total=None, desc=f"Loading {table_name}") as tracker:
                    reader = pd.read_csv(
                        file_path,
                        sep=self.delimiter,
                        chunksize=self.chunk_size,
                        usecols=lambda c: c.strip() in target_set,
                        dtype=str,
                        compression="infer",
                        encoding=self.encoding,
                        low_memory=False,
                    )

                    for chunk_index, chunk in enumerate(reader):
                        chunk.columns = [c.strip() for c in chunk.columns]

                        # First chunk validation: duplicates + missing required columns
                        if chunk_index == 0:
                            if len(chunk.columns) != len(set(chunk.columns)):
                                raise RuntimeError("Duplicate columns detected in TSV header.")
                            missing = [c for c in target_cols if c not in chunk.columns]
                            if missing:
                                raise RuntimeError(
                                    f"TSV missing columns required by target table: {missing}"
                                )

                        # Transform into exact target order + cleaning
                        chunk = chunk.reindex(columns=target_cols)
                        chunk = fix_datetime_columns(chunk)
                        chunk = self._coerce_numeric_columns(chunk, num_cols)
                        chunk = self._coerce_integer_columns(chunk, int_cols)

                        for batch in self._iter_batches(chunk):
                            loaded = self._copy_batch(cur, copy_sql, batch)
                            total_rows += loaded
                            tracker.update(loaded)

                        if (chunk_index + 1) % 5 == 0 and not progress_enable():
                            logger.info(
                                f"Processed {chunk_index + 1} chunks... Total rows: {total_rows}"
                            )

            raw_conn.commit()
            logger.success(f"TSV Load Completed: {table_name} ({total_rows} rows)")

        except Exception:
            raw_conn.rollback()
            logger.exception("Failed to load TSV data")
            raise

        finally:
            raw_conn.close()
