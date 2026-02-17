# src/dw03/pipelines/bq_run_sql.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

from loguru import logger

from dw03.adapters.bq_client import BigQueryClient
from dw03.config.settings import AppSettings
from dw03.runtime.sql_template import render_sql_template


# --- Helpers ---

def _strip_leading_comments(sql: str) -> str:
    """Removes leading SQL comments to locate the actual query start."""
    s = sql.lstrip()
    while True:
        if s.startswith("--"):
            nl = s.find("\n")
            s = "" if nl == -1 else s[nl + 1:].lstrip()
            continue
        if s.startswith("/*"):
            end = s.find("*/")
            s = "" if end == -1 else s[end + 2:].lstrip()
            continue
        return s


def is_query_statement(sql: str) -> bool:
    """Identifies if the SQL is a row-returning query (SELECT/WITH)."""
    s = _strip_leading_comments(sql).lower()
    return s.startswith("select") or s.startswith("with")


def split_sql_statements(sql: str) -> list[str]:
    """
    Splits a SQL script into individual statements by semicolon.
    Ensures semicolons inside strings or comments are ignored.
    """
    statements: list[str] = []
    buf: list[str] = []

    # State tracking for parsing
    in_single = False
    in_double = False
    in_comment = False

    i = 0
    n = len(sql)

    while i < n:
        ch = sql[i]

        # Handle comment state
        if in_comment:
            if ch == "\n":
                in_comment = False
            buf.append(ch)
            i += 1
            continue

        # Detect comment start
        if (not in_single and not in_double) and ch == "-" and i + 1 < n and sql[i + 1] == "-":
            in_comment = True
            buf.append(ch)
            buf.append(sql[i + 1])
            i += 2
            continue

        # Toggle quote states
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double

        # Split on valid semicolon
        if ch == ";" and not in_single and not in_double:
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
        else:
            buf.append(ch)

        i += 1

    # Capture trailing content
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)

    # Clean up and filter out empty or comment-only blocks
    valid_statements: list[str] = []
    for stmt in statements:
        lines = stmt.splitlines()
        code_lines = [line.strip() for line in lines if not line.strip().startswith("--")]
        if "".join(code_lines).strip():
            valid_statements.append(stmt)

    return valid_statements


# --- Main Runner ---

@dataclass(frozen=True)
class BigQuerySqlRunner:
    """Orchestrates SQL template rendering and BigQuery execution."""
    settings: AppSettings

    @classmethod
    def from_settings(cls, settings: AppSettings) -> "BigQuerySqlRunner":
        return cls(settings=settings)

    def run(
            self,
            *,
            sql_dir: str | None = None,
            sql_file: str | None = None,
            variables: dict[str, str] | None = None,
            dry_run: bool | None = None,
            stop_on_error: bool = True,
    ) -> None:
        """Entry point for running either a single file or a directory of SQL scripts."""
        resolved_dry_run = self.settings.bq_dry_run if dry_run is None else dry_run

        # Resolve target paths
        if sql_file:
            path_obj = Path(sql_file)
            if not path_obj.exists():
                raise FileNotFoundError(f"SQL file not found: {sql_file}")
            paths = [path_obj]
        else:
            dir_path = Path(sql_dir or self.settings.sql_dir)
            if not dir_path.exists() or not dir_path.is_dir():
                raise FileNotFoundError(f"SQL dir not found: {dir_path.as_posix()}")
            paths = sorted(dir_path.glob("*.sql"))

        if not paths:
            raise ValueError("No SQL files found to run.")

        self.run_files(
            sql_paths=paths,
            variables=variables,
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
        """Sequentially processes and executes a list of SQL files."""

        # Initialize BigQuery client
        bq = BigQueryClient(
            project_id=self.settings.gcp_project_id,
            location=self.settings.bq_location,
            labels={"module": "03", "app": "run_sql"},
        )

        # Merge environment settings with runtime template variables
        base_vars = self.settings.to_template_vars()
        if variables:
            base_vars.update(variables)

        logger.info(
            "Starting batch execution | Dry-run: {} | Files: {}",
            dry_run,
            [p.name for p in sql_paths]
        )
        logger.info(
            "Result printing config | Enabled: {} | Limit: {} rows",
            self.settings.sql_print_results,
            self.settings.sql_print_max_rows,
        )

        failures = 0
        total_estimated_bytes = 0

        # Loop through each SQL file
        for path in sql_paths:
            try:
                # Render Jinja2 templates and split content into statements
                sql_raw = path.read_text(encoding="utf-8")
                sql_rendered = render_sql_template(sql_raw, base_vars)
                statements = split_sql_statements(sql_rendered)
            except Exception as e:
                logger.error("Template render failed | File: {} | Error: {}", path.name, e)
                failures += 1
                if stop_on_error:
                    break
                continue

            logger.info("Processing file | Name: {} | Statements: {}", path.name, len(statements))

            # Execute individual statements
            for idx, stmt in enumerate(statements, start=1):
                label = f"{path.name}#{idx:02d}"

                try:
                    # Dry-Run Mode: Estimate cost without executing
                    if dry_run:
                        est = bq.dry_run(stmt)
                        total_estimated_bytes += est
                        size_mb = est / 1024 / 1024
                        logger.info("Dry-run passed | {} | Est. Size: {:.2f} MB", label, size_mb)
                        continue

                    # Execution Mode: Run query on BigQuery
                    job = bq.execute_job(stmt)
                    logger.info("Job submitted | Location: {} | Waiting...", self.settings.bq_location)

                    # Handle result logging for queries (SELECT/WITH)
                    if self.settings.sql_print_results and is_query_statement(stmt):
                        max_rows = int(self.settings.sql_print_max_rows)

                        it = job.result(max_results=max_rows if max_rows > 0 else None)
                        rows = [dict(r) for r in it] if max_rows != 0 else []

                        payload = {
                            "label": label,
                            "printed_rows": len(rows),
                            "rows": rows,
                        }
                        logger.success(
                            "Query successful | {} | Job ID: {}",
                            label,
                            job.job_id,
                        )
                        logger.info(
                            "Result Preview ({} rows):\n{}",
                            len(rows),
                            json.dumps(payload, default=str, ensure_ascii=False, indent=2),
                        )
                    else:
                        # Direct execution for non-query statements (DDL/DML)
                        job.result()
                        logger.success("Statement successful | {} | Job ID: {}", label, job.job_id)

                except Exception as e:
                    failures += 1
                    logger.error("Execution failed | {} | Error: {}", label, repr(e))
                    if stop_on_error:
                        break

            if failures and stop_on_error:
                break

        # Log final execution summary
        if dry_run:
            total_gb = total_estimated_bytes / (1024 ** 3)
            logger.success("Dry-run summary | Files: {} | Total Est. Size: {:.4f} GB", len(sql_paths), total_gb)

        if failures:
            raise RuntimeError(f"{failures} SQL statement(s) failed. Check logs for details.")