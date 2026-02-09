# src/dw03/pipelines/bq_run_sql.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from dw03.adapters.bq_client import BigQueryClient
from dw03.config.settings import AppSettings
from dw03.runtime.sql_template import render_sql_template


@dataclass(frozen=True)
class BigQuerySqlRunner:
    settings: AppSettings

    @classmethod
    def from_settings(cls, settings: AppSettings) -> "BigQuerySqlRunner":
        return cls(settings=settings)

    def run(
        self,
        *,
        sql_dir: str | None = None,
        sql_file: str | None = None,
        dry_run: bool | None = None,
        stop_on_error: bool = True,
    ) -> None:
        """
        Entry point used by CLI:
        - If sql_file is provided -> run that single file
        - Else run all *.sql in sql_dir (sorted)
        """
        resolved_dry_run = self.settings.bq_dry_run if dry_run is None else dry_run

        if sql_file:
            paths = [Path(sql_file)]
        else:
            dir_path = Path(sql_dir or self.settings.sql_dir)
            if not dir_path.exists():
                raise FileNotFoundError(f"SQL dir not found: {dir_path.as_posix()}")
            paths = sorted(dir_path.glob("*.sql"))

        if not paths:
            raise ValueError("No SQL files found to run.")

        self.run_files(sql_paths=paths, dry_run=resolved_dry_run, stop_on_error=stop_on_error)

    def run_files(
        self,
        *,
        sql_paths: list[Path],
        variables: dict[str, str] | None = None,
        dry_run: bool = False,
        stop_on_error: bool = True,
    ) -> None:
        bq = BigQueryClient(
            project_id=self.settings.gcp_project_id,
            location=self.settings.bq_location,
            labels={"module": "03", "app": "run_sql"},
        )

        base_vars = self.settings.to_template_vars()
        if variables:
            base_vars.update(variables)

        logger.info("Run SQL | dry_run={} | files={}", dry_run, [p.as_posix() for p in sql_paths])

        failures = 0
        total_estimated_bytes = 0

        for path in sql_paths:
            sql_raw = path.read_text(encoding="utf-8")
            sql = render_sql_template(sql_raw, base_vars)

            logger.info("SQL file: {}", path.as_posix())

            try:
                if dry_run:
                    est = bq.dry_run(sql)
                    total_estimated_bytes += est
                    logger.info("Dry-run OK | estimated_bytes={}", est)
                else:
                    job_id = bq.execute(sql)
                    logger.info("Execute OK | job_id={}", job_id)
            except Exception as e:
                failures += 1
                logger.error("SQL failed | file={} | error={}", path.as_posix(), repr(e))
                if stop_on_error:
                    break

        if dry_run:
            logger.info(
                "Dry-run summary | files={} | total_estimated_bytes={}",
                len(sql_paths),
                total_estimated_bytes,
            )

        if failures:
            raise RuntimeError(f"{failures} SQL file(s) failed. Check logs for details.")
