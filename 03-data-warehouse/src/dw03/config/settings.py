# src/dw03/config/settings.py

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(x.strip() for x in value.split(",") if x.strip())


@dataclass(frozen=True)
class AppSettings:
    # --- core ---
    gcp_project_id: str
    bq_location: str = "US"

    # --- auth (optional; usually empty if ADC) ---
    google_application_credentials: str = ""

    # --- gcs / taxi source ---
    gcs_bucket_name: str = ""
    gcs_raw_prefix: str = "raw/ny_taxi"
    taxi_color: str = "yellow"
    taxi_year: str = "2024"
    months: tuple[str, ...] = ("01", "02", "03", "04", "05", "06")
    taxi_base_url: str = ""  # optional override

    # --- bigquery datasets / tables ---
    bq_dataset_staging: str = "staging"
    bq_dataset_final: str = "final"
    bq_table_ext: str = "ny_taxi_yellow_trip_2024_ext"
    bq_table_base: str = "ny_taxi_yellow_trip_2024_base"
    bq_table_final: str = "ny_taxi_yellow_trip_2024"

    # --- sql runner ---
    sql_dir: str = "sql"
    sql_file: Optional[str] = None
    bq_dry_run: bool = True

    # --- runtime / logging ---
    log_dir: str = "./apps/logs"

    # --- downloader runtime tuning (IMPORTANT) ---
    max_workers: int = 5
    max_retries: int = 3
    http_timeout_sec: int = 300
    gcs_chunk_size: int = 8 * 1024 * 1024  # 8 MB

    @classmethod
    def from_env(cls, env_file: str = ".env") -> "AppSettings":
        # resolve repo root
        project_root = Path(__file__).resolve().parents[3]
        env_path = project_root / env_file
        load_dotenv(env_path, override=False)

        project_id = os.environ.get("GCP_PROJECT_ID", "").strip()
        if not project_id:
            raise ValueError(
                f"GCP_PROJECT_ID is required. Put it in {env_path} or export it in your shell."
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

            # --- runtime ---
            log_dir=os.getenv("LOG_DIR", "./apps/logs").strip() or "./apps/logs",

            # --- downloader tuning ---
            max_workers=int(os.getenv("MAX_WORKERS", "5")),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
            http_timeout_sec=int(os.getenv("HTTP_TIMEOUT_SEC", "300")),
            gcs_chunk_size=int(os.getenv("GCS_CHUNK_SIZE", str(8 * 1024 * 1024))),
        )

    def to_template_vars(self) -> dict[str, str]:
        """
        Variables exposed to SQL templating.
        Keep values as strings.
        """
        return {
            "GCP_PROJECT_ID": self.gcp_project_id,
            "BQ_LOCATION": self.bq_location,
            "BQ_DATASET_STAGING": self.bq_dataset_staging,
            "BQ_DATASET_FINAL": self.bq_dataset_final,
            "BQ_TABLE_EXT": self.bq_table_ext,
            "BQ_TABLE_BASE": self.bq_table_base,
            "BQ_TABLE_FINAL": self.bq_table_final,
            "GCS_BUCKET_NAME": self.gcs_bucket_name,
            "GCS_RAW_PREFIX": self.gcs_raw_prefix,
            "TAXI_COLOR": self.taxi_color,
            "TAXI_YEAR": self.taxi_year,
        }
