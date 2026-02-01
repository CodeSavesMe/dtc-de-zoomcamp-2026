# 01-docker-terraform/main.py
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import click
from dotenv import load_dotenv
from loguru import logger

from docker_ingestion_pipeline.config import (
    LoaderSettings,
    Paths,
    build_paths,
    configure_logging,
    env_get,
    env_int,
    load_loader_settings,
)
from docker_ingestion_pipeline.core.ingestion_pipeline import IngestionPipeline
from docker_ingestion_pipeline.db.client import PostgresClient
from docker_ingestion_pipeline.db.loader_csv import CsvCopyLoader
from docker_ingestion_pipeline.db.loader_parquet import ParquetStreamLoader
from docker_ingestion_pipeline.db.loader_tsv import TsvCopyLoader
from docker_ingestion_pipeline.db.lock import AdvisoryLock
from docker_ingestion_pipeline.db.optimize import PostLoadOptimizer
from docker_ingestion_pipeline.db.schema import PostgresSchemaManager
from docker_ingestion_pipeline.db.swapper import AtomicSwapper
from docker_ingestion_pipeline.db.validator_repo import PostgresStagingValidator
from docker_ingestion_pipeline.utils.file_types import FileFormat

# -----------------------------------------------------------------------------
# 1) Environment setup
# -----------------------------------------------------------------------------
# Load .env from the same folder as main.py for local development.
# In Docker/Kestra, real environment variables will override this (override=False).
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=False)


# -----------------------------------------------------------------------------
# 2) Small helpers (CLI only)
# -----------------------------------------------------------------------------
def env_bool_cli(name: str, default: bool = False) -> bool:
    """
    CLI convenience boolean parser.

    We intentionally keep this tiny and local: it only reads the current process env.
    """
    raw = env_get(__import__("os").environ, name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def normalize_month(month: str | int) -> str:
    """Ensure month is 2 digits (e.g., '1' -> '01')."""
    return str(month).strip().zfill(2)


def build_dtc_taxi_url(taxi: str, year: int, month: str, file_format: str) -> str:
    """
    Construct the GitHub download URL for DTC NYC TLC dataset releases.

    file_format controls the extension:
    - parquet -> .parquet
    - csv     -> .csv.gz
    """
    taxi = taxi.lower().strip()
    month = normalize_month(month)
    fmt = file_format.lower().strip()

    if taxi not in {"green", "yellow", "fhv"}:
        raise click.UsageError(f"Unknown taxi type: {taxi}")

    if fmt == "parquet":
        ext = "parquet"
    elif fmt == "csv":
        ext = "csv.gz"
    else:
        raise click.UsageError(f"Unsupported format for URL builder: {fmt}")

    return (
        f"https://github.com/DataTalksClub/nyc-tlc-data/releases/download/{taxi}/"
        f"{taxi}_tripdata_{year}-{month}.{ext}"
    )


def monthly_table_name(taxi: str, year: int, month: str) -> str:
    """Generate standard table name: yellow_tripdata_2024_01"""
    taxi = taxi.lower().strip()
    month = normalize_month(month)
    return f"{taxi}_tripdata_{year}_{month}"


def infer_table_name_from_url(url: str) -> str:
    """Infer table name from URL filename, handling common extensions."""
    filename = Path(urlparse(url).path).name
    name = re.sub(r"\.(csv|tsv|parquet)(\.gz)?$", "", filename, flags=re.IGNORECASE)
    return name.replace("-", "_")


# -----------------------------------------------------------------------------
# 3) Dependency Injection builders (wiring)
# -----------------------------------------------------------------------------
def build_pg_client() -> PostgresClient:
    """
    Initialize Postgres client using environment variables.

    This is wiring code (composition root), not core business logic.
    """
    import os

    db_host = env_get(os.environ, "DB_HOST", "localhost") or "localhost"
    db_port = env_int(os.environ, "DB_PORT", 5432, min_value=1)
    db_user = env_get(os.environ, "DB_USER", "postgres") or "postgres"
    db_password = env_get(os.environ, "DB_PASSWORD", "postgres") or "postgres"
    db_name = env_get(os.environ, "DB_NAME", "ny_taxi") or "ny_taxi"
    db_schema = env_get(os.environ, "DB_SCHEMA", "public") or "public"

    logger.info(f"Target DB: {db_host}:{db_port}/{db_name} (User: {db_user}, Schema: {db_schema})")

    return PostgresClient.from_params(
        user=str(db_user),
        password=str(db_password),
        host=str(db_host),
        port=int(db_port),
        db=str(db_name),
        schema=str(db_schema),
    )


def build_pipeline(pg: PostgresClient, settings: LoaderSettings) -> IngestionPipeline:
    """
    Assemble the ingestion pipeline with concrete infrastructure adapters.

    Note:
    - Core depends only on ports (interfaces).
    - Here (composition root), we inject concrete implementations.
    """
    loaders = {
        FileFormat.CSV: CsvCopyLoader(
            pg, chunk_size=settings.chunk_size, batch_size=settings.batch_size
        ),
        FileFormat.TSV: TsvCopyLoader(
            pg, chunk_size=settings.chunk_size, batch_size=settings.batch_size
        ),
        FileFormat.PARQUET: ParquetStreamLoader(
            pg, chunk_size=settings.chunk_size, batch_size=settings.batch_size
        ),
    }

    return IngestionPipeline(
        db=pg,
        lock=AdvisoryLock(pg),
        schema=PostgresSchemaManager(pg, sample_rows=2000),
        loaders=loaders,
        validator=PostgresStagingValidator(pg),
        swapper=AtomicSwapper(pg),
        optimizer=PostLoadOptimizer(pg),
    )


# -----------------------------------------------------------------------------
# 4) CLI
# -----------------------------------------------------------------------------
CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"], max_content_width=120)


@click.group(context_settings=CONTEXT_SETTINGS)
def cli() -> None:
    """
    NY TAXI DATA INGESTION TOOL

    Orchestrates the ETL process for NYC TLC Taxi Data.
    Suitable for running in Docker, Kestra, or Airflow.
    """
    paths: Paths = build_paths()
    configure_logging(paths)


@cli.command("ingest", help="Standard Ingestion: Download and load monthly taxi data.")
@click.option(
    "--taxi",
    type=click.Choice(["green", "yellow"], case_sensitive=False),
    default=lambda: env_get(__import__("os").environ, "TAXI"),
    required=True,
    help="Taxi type (GitHub folder name).",
)
@click.option(
    "--year",
    type=int,
    default=lambda: env_int(__import__("os").environ, "YEAR", 2025, min_value=1900),
    required=True,
    help="Trip year (YYYY).",
)
@click.option(
    "--month",
    type=str,
    default=lambda: env_get(__import__("os").environ, "MONTH"),
    required=True,
    help="Trip month (MM).",
)
@click.option(
    "--file-format",
    "file_format",
    type=click.Choice(["parquet", "csv"], case_sensitive=False),
    default=lambda: env_get(__import__("os").environ, "FILE_FORMAT", "parquet") or "parquet",
    show_default=True,
    help="Source file format (controls URL extension).",
)
@click.option(
    "--if-exists",
    type=click.Choice(["skip", "replace", "fail", "append"]),
    default=lambda: env_get(__import__("os").environ, "IF_EXISTS", "replace") or "replace",
    show_default=True,
    help="Strategy if table exists. 'replace' performs an Atomic Swap.",
)
@click.option(
    "--keep-local/--no-keep-local",
    default=lambda: env_bool_cli("KEEP_LOCAL", True),
    show_default=True,
    help="Retain downloaded file on disk after processing.",
)
def ingest_cmd(
    taxi: str,
    year: int,
    month: str,
    file_format: str,
    if_exists: str,
    keep_local: bool,
) -> None:
    """
    Standard ingestion workflow:
    - Build URL from taxi/year/month/format
    - Pre-flight table existence policy (skip/fail handled here)
    - Run core pipeline with (replace|append)
    """
    taxi = taxi.lower()
    month = normalize_month(month)

    try:
        url = build_dtc_taxi_url(taxi, year, month, file_format)
    except Exception as error:
        logger.error(f"Failed to build URL: {error}")
        raise SystemExit(1)

    table_name = monthly_table_name(taxi, year, month)

    logger.info("-" * 60)
    logger.info(f"JOB START: {taxi.upper()} {year}-{month}")
    logger.info(f"URL      : {url}")
    logger.info(f"Table    : {table_name}")
    logger.info(f"Policy   : {if_exists}")
    logger.info("-" * 60)

    try:
        pg = build_pg_client()

        # Pre-flight table existence policy (CLI-level)
        if pg.table_exists(table_name):
            if if_exists == "skip":
                logger.warning(f"Table {pg.schema}.{table_name} exists. Skipping.")
                return
            if if_exists == "fail":
                logger.error(f"Table {pg.schema}.{table_name} exists. Aborting.")
                raise SystemExit(2)
            if if_exists == "replace":
                logger.info("Table exists. Pipeline will use Atomic Swap (Staging -> Final).")
            if if_exists == "append":
                logger.info("Table exists. Pipeline will APPEND (Staging -> INSERT INTO Final).")

        settings = load_loader_settings()
        pipeline = build_pipeline(pg, settings)

        # Core supports only replace/append; skip/fail are handled above.
        core_strategy = "append" if if_exists == "append" else "replace"
        pipeline.run(url=url, table_name=table_name, keep_local=keep_local, if_exists=core_strategy)

        logger.success(f"Job Completed: {pg.schema}.{table_name}")

    except SystemExit:
        raise
    except Exception as error:
        logger.exception(f"Ingestion Failed: {error}")
        raise SystemExit(1)


@cli.command("ingest-url", help="Custom Ingestion: Download from an arbitrary URL.")
@click.option(
    "--url",
    default=lambda: env_get(__import__("os").environ, "DATA_URL"),
    required=True,
    help="Full URL to the raw file (Parquet/CSV/TSV).",
)
@click.option(
    "--table-name",
    default=None,
    help="Target table name (auto-inferred from filename if omitted).",
)
@click.option(
    "--if-exists",
    type=click.Choice(["skip", "replace", "fail", "append"]),
    default=lambda: env_get(__import__("os").environ, "IF_EXISTS", "replace") or "replace",
    show_default=True,
    help="Strategy if table exists.",
)
@click.option(
    "--keep-local/--no-keep-local",
    default=lambda: env_bool_cli("KEEP_LOCAL", True),
    show_default=True,
    help="Retain downloaded file on disk.",
)
def ingest_url_cmd(url: str, table_name: str | None, if_exists: str, keep_local: bool) -> None:
    """
    Custom ingestion:
    - Infer table name from URL if not provided
    - Apply pre-flight policy (skip/fail)
    - Run core pipeline (replace|append)
    """
    try:
        if not table_name:
            table_name = infer_table_name_from_url(url)

        logger.info(f"JOB START (Custom URL): {url}")
        logger.info(f"Target Table: {table_name}")
        logger.info(f"Policy      : {if_exists}")

        pg = build_pg_client()

        if pg.table_exists(table_name):
            if if_exists == "skip":
                logger.warning(f"Table {pg.schema}.{table_name} exists. Skipping.")
                return
            if if_exists == "fail":
                logger.error(f"Table {pg.schema}.{table_name} exists. Aborting.")
                raise SystemExit(2)

        settings = load_loader_settings()
        pipeline = build_pipeline(pg, settings)

        core_strategy = "append" if if_exists == "append" else "replace"
        pipeline.run(url=url, table_name=table_name, keep_local=keep_local, if_exists=core_strategy)

        logger.success(f"Job Completed: {pg.schema}.{table_name}")

    except SystemExit:
        raise
    except Exception as error:
        logger.exception(f"Custom Ingestion Failed: {error}")
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
