# dw03/pipelines/gcs_ingest.py
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple

import requests
from loguru import logger

from dw03.adapters.gcs_client import GCSStorage
from dw03.config.settings import AppSettings
from dw03.runtime.http_session import PerThreadHttpSession
from dw03.runtime.retry import should_retry_http_status, sleep_with_backoff

try:
    from google.api_core.exceptions import GoogleAPIError
except ImportError:
    GoogleAPIError = Exception  # type: ignore


def _gcs_join(*parts: str) -> str:
    """
    Safely joins GCS path segments:
    - Removes extra slashes and ignores empty parts.
    """
    cleaned: list[str] = []
    for p in parts:
        if not p:
            continue
        s = p.strip("/")
        if s:
            cleaned.append(s)
    return "/".join(cleaned)


class DownloadToGcsPipeline:
    """
    Pipeline to stream Parquet files from a source URL directly to GCS.
    Uses Hive Partitioning: gs://bucket/.../year=YYYY/month=MM/file.parquet
    """

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.gcs = GCSStorage()
        # Pool size 2 per thread handles simultaneous stream download/upload.
        self.http_sessions = PerThreadHttpSession(pool_size=2)

    def build_file_tasks(self) -> list[tuple[str, str]]:
        """Generates list of (source_url, gcs_blob_path) based on month config."""
        tasks: list[tuple[str, str]] = []

        table_name = f"{self.settings.taxi_color}_taxi"

        for month in self.settings.months:
            m = str(month).zfill(2)  # Pad month to 01..12

            m_int = int(m)
            if not (1 <= m_int <= 12):
                raise ValueError(f"Invalid month: {month} (normalized: {m})")

            filename = f"{self.settings.taxi_color}_tripdata_{self.settings.taxi_year}-{m}.parquet"
            source_url = f"{self.settings.taxi_base_url}/{filename}"

            gcs_blob_path = _gcs_join(
                self.settings.gcs_raw_prefix,
                "tlc_trip_record",
                table_name,
                f"year={self.settings.taxi_year}",
                f"month={m}",
                filename,
            )

            tasks.append((source_url, gcs_blob_path))

        return tasks

    def _exists_with_retry(self, blob) -> bool:
        """Checks if a blob exists with a short retry to ensure idempotency."""
        max_check = max(1, min(2, self.settings.max_retries))

        for attempt in range(1, max_check + 1):
            try:
                return bool(blob.exists())
            except Exception as e:
                if attempt == max_check:
                    logger.error("FAILED (exists check) | {} | {}", blob.name, repr(e))
                    raise

                logger.warning(
                    "Retryable exists-check error | Attempt {}/{} | {} | {}",
                    attempt,
                    max_check,
                    blob.name,
                    repr(e),
                )
                sleep_with_backoff(attempt)

        return False

    def download_and_upload_one(self, source_url: str, gcs_blob_path: str) -> str:
        """
        Processes a single file:
        - Checks if exists (idempotency).
        - Streams download and pipes directly to GCS upload.
        - Implements retries for HTTP and GCS API errors.
        """
        bucket = self.gcs.get_bucket(self.settings.gcs_bucket_name)
        blob = bucket.blob(gcs_blob_path)
        blob.chunk_size = self.settings.gcs_chunk_size

        gcs_uri = f"gs://{self.settings.gcs_bucket_name}/{gcs_blob_path}"

        if self._exists_with_retry(blob):
            return f"SKIPPED (exists): {gcs_uri}"

        session = self.http_sessions.get()

        for attempt in range(1, self.settings.max_retries + 1):
            try:
                logger.info("Start | Attempt {}/{} | {}", attempt, self.settings.max_retries, source_url)

                with session.get(
                    source_url,
                    stream=True,
                    timeout=(5, self.settings.http_timeout_sec),
                ) as response:
                    response.raise_for_status()

                    content_type = response.headers.get("Content-Type", "application/octet-stream")

                    # Upload raw stream; rewind=False as response.raw is a socket/stream.
                    blob.upload_from_file(
                        response.raw,
                        content_type=content_type,
                        rewind=False,
                    )

                return f"SUCCESS: {gcs_uri}"

            except requests.HTTPError as e:
                status = getattr(getattr(e, "response", None), "status_code", None)

                # Retry on unknown status until max limit.
                if status is None:
                    if attempt == self.settings.max_retries:
                        logger.error("FAILED (unknown HTTP status) | {} | {}", source_url, repr(e))
                        raise
                    logger.warning("Retryable HTTPError (unknown status) | {} | {}", source_url, repr(e))
                    sleep_with_backoff(attempt)
                    continue

                # Non-retryable client errors (4xx).
                if status in (400, 401, 403, 404):
                    logger.error("FAILED (non-retryable HTTP {}) | {}", status, source_url)
                    raise

                # Retry only on specific retryable codes (e.g., 429, 5xx).
                if not should_retry_http_status(status):
                    logger.error("FAILED (non-retryable HTTP {}) | {}", status, source_url)
                    raise

                if attempt == self.settings.max_retries:
                    logger.error("FAILED (max retries) | HTTP {} | {}", status, source_url)
                    raise

                logger.warning(
                    "Retryable HTTP {} | Attempt {}/{} | {}",
                    status,
                    attempt,
                    self.settings.max_retries,
                    source_url,
                )
                sleep_with_backoff(attempt)

            except requests.RequestException as e:
                # Handle timeouts, DNS, or connection errors.
                if attempt == self.settings.max_retries:
                    logger.error("FAILED (max retries) | RequestException | {} | {}", source_url, repr(e))
                    raise
                logger.warning(
                    "Retryable RequestException | Attempt {}/{} | {} | {}",
                    attempt,
                    self.settings.max_retries,
                    source_url,
                    repr(e),
                )
                sleep_with_backoff(attempt)

            except GoogleAPIError as e:
                # Handle transient GCS API errors.
                if attempt == self.settings.max_retries:
                    logger.error("FAILED (max retries) | GCS error | {} | {}", gcs_uri, repr(e))
                    raise
                logger.warning(
                    "Retryable GCS error | Attempt {}/{} | {} | {}",
                    attempt,
                    self.settings.max_retries,
                    gcs_uri,
                    repr(e),
                )
                sleep_with_backoff(attempt)

        raise RuntimeError(f"Unexpected loop exit: {gcs_uri}")

    def run(self) -> None:
        """Executes the pipeline using concurrent threads."""
        tasks = self.build_file_tasks()

        logger.info(
            "Config | bucket={} | raw_prefix={} | workers={} | retries={} | chunk_mb={} | months={}",
            self.settings.gcs_bucket_name,
            self.settings.gcs_raw_prefix,
            self.settings.max_workers,
            self.settings.max_retries,
            round(self.settings.gcs_chunk_size / (1024 * 1024), 2),
            self.settings.months,
        )
        logger.info("Pipeline start | files={} | workers={}", len(tasks), self.settings.max_workers)

        stats = {"success": 0, "skipped": 0, "failed": 0}
        errors: list[str] = []

        with ThreadPoolExecutor(max_workers=self.settings.max_workers) as executor:
            future_to_url = {
                executor.submit(self.download_and_upload_one, source_url, gcs_path): source_url
                for source_url, gcs_path in tasks
            }

            for future in as_completed(future_to_url):
                source_url = future_to_url[future]
                try:
                    result = future.result()
                    logger.info(result)
                    if result.startswith("SUCCESS"):
                        stats["success"] += 1
                    elif result.startswith("SKIPPED"):
                        stats["skipped"] += 1
                except Exception as e:
                    stats["failed"] += 1
                    msg = f"{source_url} failed: {repr(e)}"
                    errors.append(msg)
                    logger.error(msg)

        logger.info(
            "Summary | success={} | skipped={} | failed={}",
            stats["success"],
            stats["skipped"],
            stats["failed"],
        )

        if errors:
            raise RuntimeError(
                f"Pipeline finished with {len(errors)} error(s). Check logs for details."
            )