# docker_ingestion_pipeline/core/ingestion_pipeline.py
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from time import time
from typing import TYPE_CHECKING

from loguru import logger

from docker_ingestion_pipeline.utils.downloader import download_file
from docker_ingestion_pipeline.utils.file_types import FileFormat, detect_file_format
from docker_ingestion_pipeline.utils.identifiers import sanitize_ident

if TYPE_CHECKING:
    from docker_ingestion_pipeline.ports.database import Database
    from docker_ingestion_pipeline.ports.loader import Loader
    from docker_ingestion_pipeline.ports.lock import LockManager
    from docker_ingestion_pipeline.ports.optimize import Optimizer
    from docker_ingestion_pipeline.ports.schema import SchemaManager
    from docker_ingestion_pipeline.ports.swapper import Swapper
    from docker_ingestion_pipeline.ports.validator import Validator


class UnsupportedStrategyError(ValueError):
    """Raised when the ingestion strategy is not supported by the core pipeline."""


class LoaderNotConfiguredError(ValueError):
    """Raised when no loader exists for a detected file format."""


@dataclass(frozen=True)
class IngestionPipeline:
    """
    Ingestion use-case (application core).

    Rules:
    - This module must depend on PORTS (interfaces), not infrastructure libraries.
    - All SQLAlchemy/psycopg details live in adapters (db/*).
    """

    db: Database
    lock: LockManager
    schema: SchemaManager
    loaders: Mapping[FileFormat, Loader]
    validator: Validator
    swapper: Swapper
    optimizer: Optimizer

    # ------------------------------------------------------------------
    # Small helpers (keep orchestration readable)
    # ------------------------------------------------------------------
    def _get_loader(self, fmt: FileFormat) -> Loader:
        loader = self.loaders.get(fmt)
        if loader is None:
            raise LoaderNotConfiguredError(f"No loader configured for format: {fmt}")
        return loader

    def _staging_table_name(self, final_table: str) -> str:
        return f"{final_table}__staging"

    def _lock_key(self, schema: str, table: str) -> str:
        return f"ingest:{schema}:{table}"

    def _cleanup_staging_best_effort(self, staging_table: str) -> None:
        """
        Best-effort cleanup so retries don't leave a lot of staging tables around.
        Never raise from cleanup to avoid masking the original failure.
        """
        try:
            self.db.drop_table_if_exists(staging_table)
        except Exception:
            logger.warning("Failed to drop staging table during cleanup (best-effort).")

    def _cleanup_file_best_effort(self, file_path: str, keep_local: bool) -> None:
        """Remove local file only if requested; ignore cleanup errors."""
        if keep_local:
            return
        if not os.path.exists(file_path):
            return
        try:
            os.remove(file_path)
        except Exception:
            logger.warning(f"Failed to remove local file: {file_path}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(
        self,
        url: str,
        table_name: str,
        keep_local: bool = True,
        if_exists: str = "replace",
    ) -> None:
        """
        End-to-end ingestion flow:
          download -> ensure schema -> staging load -> validate -> (append|swap) -> analyze

        Notes:
        - CLI-level policies like 'skip' and 'fail' should be handled BEFORE calling this method.
        - Core supports only two behaviors:
            * replace: staging -> final via atomic swap
            * append : staging -> final via INSERT ... SELECT
        """
        final_table = sanitize_ident(table_name)
        staging_table = sanitize_ident(self._staging_table_name(final_table))

        schema_name = getattr(self.db, "schema", "public")
        lock_key = self._lock_key(schema_name, final_table)

        if if_exists not in {"replace", "append"}:
            raise UnsupportedStrategyError(f"Unsupported if_exists strategy: {if_exists!r}")

        # Download locally (downloader handles caching/atomic writes)
        file_path = download_file(url)
        fmt = detect_file_format(file_path)

        start_ts = time()

        try:
            with self.lock.acquire(lock_key):
                # 1) Ensure final table exists (bootstrap once)
                if not self.db.table_exists(final_table):
                    self.schema.ensure_final_schema(file_path=file_path, final_table=final_table)

                # 2) Recreate staging LIKE final
                self.schema.recreate_staging_like_final(
                    final_table=final_table, staging_table=staging_table
                )

                # 3) Load into staging based on detected file format
                loader = self._get_loader(fmt)
                loader.load(file_path=file_path, table_name=staging_table)

                # 4) Validate staging
                expected_month = self.validator.infer_expected_month_from_table(final_table)
                if not expected_month:
                    logger.debug(
                        f"No YYYY_MM pattern in table_name={final_table}; month spillover check will be skipped."
                    )
                self.validator.validate_staging(staging_table, expected_month=expected_month)

                # 5) Apply load strategy
                if if_exists == "append":
                    inserted = self.db.append_from_staging(
                        final_table=final_table, staging_table=staging_table
                    )
                    logger.info(f"Append completed: inserted_rows={inserted}")
                    self.db.drop_table_if_exists(staging_table)
                else:
                    self.swapper.swap_tables_atomically(
                        final_table=final_table, staging_table=staging_table
                    )

                # 6) Post-load optimization
                self.optimizer.analyze(final_table)

            elapsed = time() - start_ts
            logger.success(f"Ingestion complete in <green>{elapsed:.2f}</green>s")

        except Exception as e:
            logger.exception(f"Ingestion failed: {e}")
            self._cleanup_staging_best_effort(staging_table)
            raise

        finally:
            self._cleanup_file_best_effort(file_path=file_path, keep_local=keep_local)
