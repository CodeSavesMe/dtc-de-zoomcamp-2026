# docker-ingestion-pipeline/utils/datetime_fix.py

from __future__ import annotations

import pandas as pd
from loguru import logger


def fix_datetime_columns(df: pd.DataFrame) -> pd.DataFrame:
    datetime_cols = [
        ("tpep_pickup_datetime", "tpep_dropoff_datetime"),
        ("lpep_pickup_datetime", "lpep_dropoff_datetime"),
        ("pickup_datetime", "dropoff_datetime"),
    ]

    for pickup, dropoff in datetime_cols:
        # Check if columns exist (case-insensitive check handled by pandas usually,
        # but here we rely on exact match or cleaned headers)
        if pickup in df.columns and dropoff in df.columns:
            logger.debug(f"Converting columns {pickup} and {dropoff} to datetime")
            df[pickup] = pd.to_datetime(df[pickup], errors="coerce")
            df[dropoff] = pd.to_datetime(df[dropoff], errors="coerce")

    return df
