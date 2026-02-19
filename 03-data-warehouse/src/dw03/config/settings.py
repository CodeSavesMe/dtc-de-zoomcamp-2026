# src/dw03/config/settings.py

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def _split_csv(value: str) -> tuple[str, ...]:
    """Splits a comma-separated string into a trimmed tuple."""
    return tuple(x.strip() for x in value.split(",") if x.strip())


@dataclass(frozen=True)
class AppSettings:
    # --- GCP Core ---
    gcp_project_id: str
    bq_location: str = "US"

    # --- Authentication ---
    google_application_credentials: str = ""

    # --- GCS / Taxi Source ---
    gcs_bucket_name: str = ""
    gcs_raw_prefix: str = "raw/ny_taxi"
    taxi_color: str = "yellow"
    taxi_year: str = "2024"
    months: tuple[str, ...] = ("01", "02", "03", "04", "05", "06")
    taxi_base_url: str = "" 

    # --- BigQuery Dataset & Tables ---
    bq_dataset_staging: str = "staging"
    bq_dataset_final: str = "final"
    bq_table_ext: str = "ny_taxi_yellow_trip_2024_ext"
    bq_table_base: str = "ny_taxi_yellow_trip_2024_base"
    bq_table_final: str = "ny_taxi_yellow_trip_2024"

    # --- SQL Runner Config ---
    sql_dir: str = "sql"
    sql_file: Optional[str] = None
    bq_dry_run: bool = True
    sql_print_results: bool = False
    sql_print_max_rows: int = 20

    # --- Runtime & Logging ---
    log_dir: str = "./apps/logs"

    # --- Downloader Tuning ---
    max_workers: int = 5
    max_retries: int = 3
    http_timeout_sec: int = 300
    gcs_chunk_size: int = 8 * 1024 * 1024  # 8 MB

    @classmethod
    def from_env(cls, env_file: str = ".env") -> "AppSettings":
        """Loads configuration from environment variables or .env file."""
        # Resolve project root path
        project_root = Path(__file__).resolve().parents[3]
        env_path = project_root / env_file
        load_dotenv(env_path, override=False)

        project_id = os.environ.get("GCP_PROJECT_ID", "").strip()
        if not project_id:
            raise ValueError(
                f"GCP_PROJECT_ID is required in {env_path} or environment."
            )

        return cls(
            # --- core ---
            gcp_project_id=project_id,
            bq_location=os.getenv("BQ_LOCATION", "US").strip() or "US",

            # --- auth ---
            google_application_credentials=os.getenv(
                "GOOGLE_APPLICATION_CREDENTIALS", ""
            ).strip(),

            # --- gcs / taxi ---
            gcs_bucket_name=os.getenv("GCS_BUCKET_NAME", "").strip(),
            gcs_raw_prefix=os.getenv("GCS_RAW_PREFIX", "raw/ny_taxi").strip().strip("/"),
            taxi_color=os.getenv("TAXI_COLOR", "yellow").strip() or "yellow",
            taxi_year=os.getenv("TAXI_YEAR", "2024").strip() or "2024",
            months=_split_csv(os.getenv("MONTHS", "01,02,03,04,05,06")),
            taxi_base_url=os.getenv("TAXI_BASE_URL", "").strip(),

            # --- bigquery ---
            bq_dataset_staging=os.getenv("BQ_DATASET_STAGING", "staging").strip() or "staging",
            bq_dataset_final=os.getenv("BQ_DATASET_FINAL", "final").strip() or "final",
            bq_table_ext=os.getenv(
                "BQ_TABLE_EXT", "ny_taxi_yellow_trip_2024_ext"
            ).strip() or "ny_taxi_yellow_trip_2024_ext",
            bq_table_base=os.getenv(
                "BQ_TABLE_BASE", "ny_taxi_yellow_trip_2024_base"
            ).strip() or "ny_taxi_yellow_trip_2024_base",
            bq_table_final=os.getenv(
                "BQ_TABLE_FINAL", "ny_taxi_yellow_trip_2024"
            ).strip() or "ny_taxi_yellow_trip_2024",

            # --- sql runner ---
            sql_dir=os.getenv("SQL_DIR", "sql").strip() or "sql",
            sql_file=os.getenv("SQL_FILE", "").strip() or None,
            bq_dry_run=os.getenv("BQ_DRY_RUN", "true").lower() in ("1", "true", "yes", "y"),
            sql_print_results=os.getenv("SQL_PRINT_RESULTS", "false").lower() in ("1", "true", "yes", "y"),
            sql_print_max_rows=max(0, int(os.getenv("SQL_PRINT_MAX_ROWS", "20"))),

            # --- runtime ---
            log_dir=os.getenv("LOG_DIR", "./apps/logs").strip() or "./apps/logs",

            # --- downloader tuning ---
            max_workers=int(os.getenv("MAX_WORKERS", "5")),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
            http_timeout_sec=int(os.getenv("HTTP_TIMEOUT_SEC", "300")),
            gcs_chunk_size=int(os.getenv("GCS_CHUNK_SIZE", str(8 * 1024 * 1024))),
        )


    def to_template_vars(self) -> dict[str, str]:
        """Maps settings to variables for SQL Jinja2 templates."""
        # Normalize GCS path prefix
        raw_prefix = (self.gcs_raw_prefix or "").strip("/")
        raw_prefix_slash = f"{raw_prefix}/" if raw_prefix else ""

        # Construct base GCS paths
        taxi_table_name = f"{self.taxi_color}_taxi"
        gcs_trip_root = (
            f"gs://{self.gcs_bucket_name}/"
            f"{raw_prefix_slash}tlc_trip_record/{taxi_table_name}"
        )

        # Mapping: Pickup timestamp column by taxi type
        pickup_col_by_color = {
            "yellow": "tpep_pickup_datetime",
            "green": "lpep_pickup_datetime",
            "fhv": "pickup_datetime",
        }
        pickup_col = pickup_col_by_color.get(self.taxi_color, "pickup_datetime")

        # Mapping: Cluster columns by taxi type
        cluster_cols_by_color = {
            "yellow": "PULocationID, DOLocationID, VendorID",
            "green": "PULocationID, DOLocationID, VendorID",
            "fhv": "dispatching_base_num",
        }
        cluster_cols = cluster_cols_by_color.get(self.taxi_color, "")

        # Handling Schema Drift: Exclude problematic columns per dataset
        except_cols = ""
        if self.taxi_color == "green":
            # Fix ehail_fee type mismatch (common in 2019/2020 files)
            except_cols = "ehail_fee"
        elif self.taxi_color == "yellow":
            # Fix airport_fee type mismatch (inconsistent INT32/DOUBLE across 2019 and 2020)
            except_cols = "airport_fee"

        return {
            "GCP_PROJECT_ID": self.gcp_project_id,
            "BQ_LOCATION": self.bq_location,

            "BQ_DATASET_STAGING": self.bq_dataset_staging,
            "BQ_DATASET_FINAL": self.bq_dataset_final,
            "BQ_TABLE_EXT": self.bq_table_ext,
            "BQ_TABLE_BASE": self.bq_table_base,
            "BQ_TABLE_FINAL": self.bq_table_final,

            "TAXI_COLOR": self.taxi_color,
            "TAXI_YEAR": self.taxi_year,
            "TAXI_TABLE_NAME": taxi_table_name,

            "GCS_BUCKET_NAME": self.gcs_bucket_name,
            "GCS_RAW_PREFIX": raw_prefix,

            "GCS_TRIP_ROOT": gcs_trip_root,
            "GCS_TRIP_GLOB": f"{gcs_trip_root}/*",
            "GCS_TRIP_HIVE_PREFIX": f"{gcs_trip_root}/",

            "TAXI_PICKUP_TS_COL": pickup_col,
            "TAXI_CLUSTER_COLS": cluster_cols,
            "TAXI_EXCEPT_COLS": except_cols,

            # Legacy alias support
            "GCS_TLC_URI_PREFIX": f"{gcs_trip_root}/",
        }