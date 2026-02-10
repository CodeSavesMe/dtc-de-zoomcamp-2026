# main.py

from __future__ import annotations

import dataclasses
import sys
from typing import Optional

import click
from loguru import logger

from dw03.config.settings import AppSettings
from dw03.pipelines.bq_run_sql import BigQuerySqlRunner
from dw03.pipelines.gcs_ingest import DownloadToGcsPipeline
from dw03.runtime.setup_loging import setup_logging


def _apply_overrides(
    settings: AppSettings,
    *,
    months: Optional[str] = None,
    sql_file: Optional[str] = None,
    sql_dir: Optional[str] = None,
    dry_run: Optional[bool] = None,
) -> AppSettings:
    """
    Return a NEW settings object with CLI overrides applied.
    Safe for frozen dataclass.
    """
    updates: dict[str, object] = {}

    if months:
        updates["months"] = tuple(m.strip() for m in months.split(",") if m.strip())

    if sql_file:
        updates["sql_file"] = sql_file

    if sql_dir:
        updates["sql_dir"] = sql_dir

    if dry_run is not None:
        updates["bq_dry_run"] = dry_run

    return dataclasses.replace(settings, **updates) if updates else settings


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def cli() -> None:
    """Module 03 - Data Warehouse (GCS + BigQuery)."""


@cli.command("show-config")
def show_config() -> None:
    """Print resolved settings (safe fields only)."""
    settings = AppSettings.from_env()
    setup_logging(settings.log_dir)

    safe = {
        "gcp_project_id": settings.gcp_project_id,
        "bq_location": settings.bq_location,
        "gcs_bucket_name": settings.gcs_bucket_name,
        "gcs_raw_prefix": settings.gcs_raw_prefix,
        "taxi_color": settings.taxi_color,
        "taxi_year": settings.taxi_year,
        "months": settings.months,
        "sql_dir": settings.sql_dir,
        "sql_file": settings.sql_file,
        "bq_dry_run": settings.bq_dry_run,
        "log_dir": settings.log_dir,
    }

    for k, v in safe.items():
        logger.info("{} = {}", k, v)


@cli.command("download-to-gcs")
@click.option("--months", default=None, help='Override MONTHS, e.g. "01,02,03,04,05,06"')
def download_to_gcs(months: Optional[str]) -> None:
    """Download NYC taxi parquet files and upload to GCS (streaming)."""
    settings = AppSettings.from_env()
    settings = _apply_overrides(settings, months=months)
    setup_logging(settings.log_dir)

    try:
        logger.info("Starting: download-to-gcs")
        DownloadToGcsPipeline(settings).run()
        logger.info("Done: download-to-gcs")
    except Exception as e:
        logger.exception("download-to-gcs failed: {}", e)
        sys.exit(1)


@cli.command("run-sql")
@click.option("--file", "sql_file", default=None, help="Run a single SQL file path.")
@click.option("--dir", "sql_dir", default=None, help="Run all *.sql in a directory (sorted).")
@click.option(
    "--dry-run/--execute",
    default=True,
    help="Dry-run estimates bytes. Use --execute to run queries.",
)
def run_sql(sql_file: Optional[str], sql_dir: Optional[str], dry_run: bool) -> None:
    """Run BigQuery SQL scripts with dry-run or execute."""
    settings = AppSettings.from_env()
    settings = _apply_overrides(settings, sql_file=sql_file, sql_dir=sql_dir, dry_run=dry_run)
    setup_logging(settings.log_dir)

    try:
        logger.info("Starting: run-sql (dry_run={})", settings.bq_dry_run)
        runner = BigQuerySqlRunner.from_settings(settings)
        runner.run(sql_dir=settings.sql_dir, sql_file=settings.sql_file, dry_run=settings.bq_dry_run)
        logger.info("Done: run-sql")
    except Exception as e:
        logger.exception("run-sql failed: {}", e)
        sys.exit(1)


if __name__ == "__main__":
    cli()
