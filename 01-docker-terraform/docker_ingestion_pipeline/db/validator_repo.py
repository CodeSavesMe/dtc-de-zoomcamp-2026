# docker_ingestion_pipeline/db/validator_repo.py
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from loguru import logger
from sqlalchemy import text

from docker_ingestion_pipeline.db.client import PostgresClient
from docker_ingestion_pipeline.ports.validator import Validator
from docker_ingestion_pipeline.utils.identifiers import qident, sanitize_ident


@dataclass(frozen=True)
class PostgresStagingValidator(Validator):
    """
    Postgres staging validator (infrastructure adapter).

    Validations:
    - Rowcount must be > 0
    - If a datetime column is detected and expected_month is provided:
        * compute spillover rows outside the expected month window
        * warn or fail depending on thresholds/config
    """

    db: PostgresClient

    # Absolute maximum number of rows allowed outside the expected month
    max_outside_month_abs: int = 200

    # Maximum ratio of rows allowed outside the expected month
    max_outside_month_ratio: float = 0.005

    # If True, validation will raise when spillover exceeds thresholds
    fail_on_outside_month: bool = False

    def _detect_datetime_column(self, table_name: str) -> str | None:
        """
        Detect a datetime column used for month spillover validation.

        We keep a small list of known NYC TLC pickup datetime column names.
        """
        table_name = sanitize_ident(table_name)

        candidates = [
            "lpep_pickup_datetime",
            "tpep_pickup_datetime",
            "pickup_datetime",
        ]

        columns = self.db.get_table_columns(table_name)
        norm_map = {c.strip().lower(): c for c in columns}

        for cand in candidates:
            key = cand.strip().lower()
            if key in norm_map:
                return norm_map[key]

        logger.debug(f"Datetime column not found for {table_name}. Columns: {columns}")
        return None

    def infer_expected_month_from_table(self, table_name: str) -> str | None:
        """
        Extract expected YYYY_MM from a table name.

        Example:
          yellow_tripdata_2024_01 -> 2024_01
        """
        m = re.search(r"(\d{4})_(\d{2})", table_name)
        if m:
            return f"{m.group(1)}_{m.group(2)}"
        return None

    def _month_window(self, expected_month: str) -> tuple[datetime, datetime]:
        """
        Convert YYYY_MM into [start, end) datetime window.
        """
        yyyy, mm = expected_month.split("_")
        year = int(yyyy)
        month = int(mm)

        start = datetime(year, month, 1)
        end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
        return start, end

    def validate_staging(
        self, staging_table: str, expected_month: str | None = None
    ) -> dict[str, Any]:
        staging_table = sanitize_ident(staging_table)
        dt_col = self._detect_datetime_column(staging_table)

        result: dict[str, Any] = {"datetime_col": dt_col}

        # Use a single connection for all validations to reduce overhead.
        with self.db.connect() as conn:
            rowcount = conn.execute(
                text(f"SELECT COUNT(*) FROM {qident(staging_table)}")
            ).scalar_one()

            result["rowcount"] = int(rowcount)

            if dt_col:
                r = (
                    conn.execute(
                        text(
                            f"""
                        SELECT
                          MIN({qident(dt_col)}) AS min_dt,
                          MAX({qident(dt_col)}) AS max_dt,
                          COUNT(*) FILTER (WHERE {qident(dt_col)} IS NULL) AS null_dt
                        FROM {qident(staging_table)}
                        """
                        )
                    )
                    .mappings()
                    .one()
                )

                result.update(
                    {
                        "min_dt": r["min_dt"],
                        "max_dt": r["max_dt"],
                        "null_dt": int(r["null_dt"]),
                    }
                )

            # Fail fast: staging cannot be empty
            if result["rowcount"] == 0:
                logger.info(f"Validation result: {result}")
                raise RuntimeError("Validation failed: staging table has 0 rows")

            # Optional: month spillover validation (only if we can do it meaningfully)
            if expected_month and dt_col:
                try:
                    start, end = self._month_window(expected_month)

                    counts = (
                        conn.execute(
                            text(
                                f"""
                            SELECT
                              COUNT(*) FILTER (
                                WHERE {qident(dt_col)} < :start OR {qident(dt_col)} >= :end
                              ) AS outside_month,
                              COUNT(*) FILTER (
                                WHERE {qident(dt_col)} >= :start AND {qident(dt_col)} < :end
                              ) AS inside_month
                            FROM {qident(staging_table)}
                            """
                            ),
                            {"start": start, "end": end},
                        )
                        .mappings()
                        .one()
                    )

                    outside = int(counts["outside_month"])
                    inside = int(counts["inside_month"])
                    ratio = (outside / result["rowcount"]) if result["rowcount"] else 0.0

                    result.update(
                        {
                            "expected_month": expected_month,
                            "inside_month": inside,
                            "outside_month": outside,
                            "outside_ratio": ratio,
                        }
                    )

                    exceeds = (outside > self.max_outside_month_abs) or (
                        ratio > self.max_outside_month_ratio
                    )

                    if exceeds:
                        msg = (
                            f"Month spillover exceeds thresholds for {expected_month}: "
                            f"outside={outside}/{result['rowcount']} ({ratio:.4%}). "
                            f"min={result.get('min_dt')}, max={result.get('max_dt')}"
                        )
                        if self.fail_on_outside_month:
                            logger.info(f"Validation result: {result}")
                            raise RuntimeError(msg)
                        logger.warning(msg)
                    else:
                        logger.info(
                            f"Month spillover within tolerance for {expected_month}: "
                            f"outside={outside}/{result['rowcount']} ({ratio:.4%})."
                        )

                except Exception as e:
                    # Non-critical: if parsing fails or dt logic breaks, don't stop ingestion.
                    logger.warning(f"Month validation skipped/failed: {e}")

        logger.info(f"Validation result: {result}")
        return result
