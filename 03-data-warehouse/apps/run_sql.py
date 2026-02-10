# apps/run_sql.py

"""
Run BigQuery SQL files (dry-run or execute).

Examples:
  uv run python apps/run_sql.py --file sql/01_create_external_table.sql --dry-run
  uv run python apps/run_sql.py --file sql/01_create_external_table.sql --execute
  uv run python apps/run_sql.py --dir sql --execute
  uv run python apps/run_sql.py --files sql/00_dataset_sanity.sql sql/01_create_external_table.sql --execute

Templating:
  SQL uses {{...}} variables from AppSettings.to_template_vars().
  You can override/add variables with: --var key=value (repeatable).
"""


from __future__ import annotations

import argparse
from pathlib import Path

from loguru import logger

from dw03.config.settings import AppSettings
from dw03.pipelines.bq_run_sql import BigQuerySqlRunner
from dw03.runtime.setup_loging import setup_logging


_ALIAS_TO_CANONICAL = {
    # core
    "project_id": "GCP_PROJECT_ID",
    "location": "BQ_LOCATION",
    # datasets
    "dataset_staging": "BQ_DATASET_STAGING",
    "dataset_final": "BQ_DATASET_FINAL",
    # tables
    "table_ext": "BQ_TABLE_EXT",
    "table_base": "BQ_TABLE_BASE",
    "table_final": "BQ_TABLE_FINAL",
    # gcs
    "bucket_name": "GCS_BUCKET_NAME",
    "raw_prefix": "GCS_RAW_PREFIX",
    "taxi_color": "TAXI_COLOR",
    "taxi_year": "TAXI_YEAR",
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run BigQuery SQL file(s) with templating.")

    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", dest="sql_file", help="Run a single SQL file.")
    group.add_argument("--dir", dest="sql_dir", help="Run all *.sql in a directory (sorted).")
    group.add_argument(
        "--files",
        nargs="+",
        help="Run multiple SQL files in the given order.",
    )

    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Dry-run only (estimate bytes).")
    mode.add_argument("--execute", action="store_true", help="Execute queries (default is dry-run).")

    p.add_argument(
        "--var",
        action="append",
        default=[],
        help="Template variables: key=value (repeatable). Example: --var dataset_staging=staging",
    )

    p.add_argument(
        "--stop-on-error/--continue-on-error",
        default=True,
        help="Stop immediately when a file fails (default: stop).",
    )

    return p


def parse_vars(items: list[str]) -> dict[str, str]:
    """
    Parse --var key=value entries.

    - Supports beginner aliases (e.g., dataset_staging) mapped to canonical keys
      used by SQL templates (e.g., BQ_DATASET_STAGING).
    - Unknown keys are passed through as-is.
    """
    out: dict[str, str] = {}

    for item in items:
        if "=" not in item:
            raise ValueError(f"Invalid --var '{item}'. Use key=value.")
        k, v = item.split("=", 1)
        key = k.strip()
        val = v.strip()

        canonical = _ALIAS_TO_CANONICAL.get(key, key)
        out[canonical] = val

    # optional helper var
    # if user passes gcs_uri we keep it as-is, otherwise BigQuery SQL can build from pieces.
    return out


def resolve_sql_paths(args: argparse.Namespace) -> list[Path]:
    if args.sql_file:
        return [Path(args.sql_file)]
    if args.files:
        return [Path(p) for p in args.files]
    if args.sql_dir:
        d = Path(args.sql_dir)
        if not d.exists() or not d.is_dir():
            raise ValueError(f"--dir must be an existing directory. Got: {d}")
        return sorted(d.glob("*.sql"))
    raise RuntimeError("No SQL input specified.")


def main() -> None:
    args = build_parser().parse_args()

    settings = AppSettings.from_env()
    setup_logging(settings.log_dir)

    sql_paths = resolve_sql_paths(args)
    user_vars = parse_vars(args.var)

    # default is dry-run unless user explicitly --execute
    dry_run = True
    if args.execute:
        dry_run = False
    elif args.dry_run:
        dry_run = True

    logger.info("Run SQL | dry_run={} | files={}", dry_run, [p.as_posix() for p in sql_paths])

    runner = BigQuerySqlRunner(settings=settings)
    runner.run_files(
        sql_paths=sql_paths,
        variables=user_vars,
        dry_run=dry_run,
        stop_on_error=args.stop_on_error,
    )


if __name__ == "__main__":
    main()
