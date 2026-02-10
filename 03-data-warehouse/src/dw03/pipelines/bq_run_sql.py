# src/dw03/pipelines/bq_run_sql.py

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from dw03.adapters.bq_client import BigQueryClient
from dw03.config.settings import AppSettings
from dw03.runtime.sql_template import render_sql_template


def split_sql_statements(sql: str) -> list[str]:
    """
    Split a SQL script into statements using ';'.

    - Does not split inside single/double-quoted strings.
    - Removes empty statements and lines that are only '--' comments.
    - Intended for simple multi-statement .sql files used in this module.
    """
    statements: list[str] = []
    buf: list[str] = []

    in_single = False
    in_double = False

    for ch in sql:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double

        if ch == ";" and not in_single and not in_double:
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
        else:
            buf.append(ch)

    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)

    # Remove statements that are only comments/whitespace.
    cleaned: list[str] = []
    for stmt in statements:
        lines = []
        for ln in stmt.splitlines():
            s = ln.strip()
            if not s:
                continue
            if s.startswith("--"):
                continue
            lines.append(ln)
        if lines:
            cleaned.append("\n".join(lines).strip())

    return cleaned


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
        Run SQL from a file or a directory.

        - If sql_file is set: run that file.
        - Else: run all *.sql in sql_dir (sorted).
        """
        resolved_dry_run = self.settings.bq_dry_run if dry_run is None else dry_run

        if sql_file:
            paths = [Path(sql_file)]
        else:
            dir_path = Path(sql_dir or self.settings.sql_dir)
            if not dir_path.exists() or not dir_path.is_dir():
                raise FileNotFoundError(f"SQL dir not found: {dir_path.as_posix()}")
            paths = sorted(dir_path.glob("*.sql"))

        if not paths:
            raise ValueError("No SQL files found to run.")

        self.run_files(
            sql_paths=paths,
            variables=None,
            dry_run=resolved_dry_run,
            stop_on_error=stop_on_error,
        )

    def run_files(
        self,
        *,
        sql_paths: list[Path],
        variables: dict[str, str] | None = None,
        dry_run: bool = False,
        stop_on_error: bool = True,
    ) -> None:
        """
        Run one or more SQL files.

        - Renders templates using settings variables plus optional overrides.
        - Supports multi-statement files by splitting on ';'.
        - Executes statements in order.
        """
        bq = BigQueryClient(
            project_id=self.settings.gcp_project_id,
            location=self.settings.bq_location,
            labels={"module": "03", "app": "run_sql"},
        )

        # Template variables from settings.
        base_vars = self.settings.to_template_vars()

        # Optional overrides (from CLI --var).
        if variables:
            base_vars.update(variables)

        logger.info("Run SQL | dry_run={} | files={}", dry_run, [p.as_posix() for p in sql_paths])

        failures = 0
        total_estimated_bytes = 0
        total_statements = 0

        for path in sql_paths:
            if not path.exists():
                raise FileNotFoundError(f"SQL file not found: {path.as_posix()}")

            sql_raw = path.read_text(encoding="utf-8")
            sql_rendered = render_sql_template(sql_raw, base_vars)

            # Split file into statements (supports multi-statement SQL files).
            statements = split_sql_statements(sql_rendered)

            logger.info("SQL file: {} | statements={}", path.as_posix(), len(statements))

            if not statements:
                logger.warning("Skip empty SQL file: {}", path.as_posix())
                continue

            for idx, stmt in enumerate(statements, start=1):
                total_statements += 1
                label = f"{path.as_posix()}#{idx:02d}"  # statement label for logs

                try:
                    if dry_run:
                        est = bq.dry_run(stmt)
                        total_estimated_bytes += est
                        logger.info("Dry-run OK | file={} | estimated_bytes={}", label, est)
                    else:
                        job_id = bq.execute(stmt)
                        logger.info("Execute OK | file={} | job_id={}", label, job_id)

                except Exception as e:
                    failures += 1
                    logger.error("SQL failed | file={} | error={}", label, repr(e))
                    if stop_on_error:
                        break

            if failures and stop_on_error:
                break

        if dry_run:
            logger.info(
                "Dry-run summary | files={} | statements={} | total_estimated_bytes={}",
                len(sql_paths),
                total_statements,
                total_estimated_bytes,
            )

        if failures:
            raise RuntimeError(f"{failures} SQL statement(s) failed. Check logs for details.")
