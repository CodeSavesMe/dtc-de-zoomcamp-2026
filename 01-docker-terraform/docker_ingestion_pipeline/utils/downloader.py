# docker_ingestion_pipeline/utils/downloader.py
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests
from loguru import logger

from docker_ingestion_pipeline.config import build_paths


@dataclass(frozen=True)
class DownloadResult:
    """Small value object for debugging/telemetry if needed."""

    url: str
    path: str
    from_cache: bool


def _safe_filename_from_url(url: str) -> str:
    """
    Extract a safe filename from URL path.
    - Prevents accidental directory traversal (e.g. '../../file').
    - Falls back to a generic name if URL path has no basename.
    """
    parsed = urlparse(url)
    name = Path(parsed.path).name
    name = name.strip()

    if not name:
        raise ValueError("URL is invalid or file name could not be determined")

    # Ensure filename only (drop any strange path parts)
    return Path(name).name


def _is_valid_cached_file(path: Path) -> bool:
    """A cached file is considered valid if it exists and has non-zero size."""
    return path.exists() and path.is_file() and path.stat().st_size > 0


def _stream_download_to_temp(
    url: str, temp_path: Path, *, timeout_s: float, chunk_bytes: int
) -> None:
    """
    Download URL to a temp file path via streaming.
    Uses a requests Session for connection reuse.
    """
    # NOTE: We keep retries simple & explicit to avoid hidden behavior.
    # Only retry on transient network/server failures.
    session = requests.Session()

    last_exc: Exception | None = None
    for attempt in range(1, 4):  # 3 attempts
        try:
            with session.get(url, stream=True, timeout=timeout_s) as r:
                # Raise for HTTP errors (404, 403, 500, etc.)
                r.raise_for_status()

                with temp_path.open("wb") as f:
                    for chunk in r.iter_content(chunk_size=chunk_bytes):
                        if chunk:
                            f.write(chunk)
            return

        except requests.HTTPError as e:
            # HTTP errors are usually not retryable (especially 4xx).
            status = getattr(e.response, "status_code", None)
            logger.error(f"HTTP error downloading {url} (status={status})")
            raise

        except (requests.Timeout, requests.ConnectionError) as e:
            last_exc = e
            logger.warning(f"Transient network error (attempt {attempt}/3): {e}")
            if attempt == 3:
                raise
            continue

        except Exception as e:
            # Unknown errors: don't spin; fail fast.
            last_exc = e
            raise

    if last_exc:
        raise last_exc


def download_file(url: str) -> str:
    """
    Download a file from a URL using an atomic write pattern.

    Behavior:
    - If cached file exists and size > 0, skip download.
    - Otherwise download to <file>.part and atomically replace on success.
    """
    paths = build_paths()  # creates data/log dirs if missing
    file_name = _safe_filename_from_url(url)

    final_path = Path(paths.data_dir) / file_name
    temp_path = Path(str(final_path) + ".part")

    # 1) Cache check
    if _is_valid_cached_file(final_path):
        logger.info(f"File already exists. Skipping download: {final_path.name}")
        return str(final_path)

    logger.info(f"Downloading data: {url} -> {final_path}")

    # 2) Download to temp file (atomic pattern)
    try:
        # Ensure no stale partial file from previous failures
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                logger.warning(f"Could not remove stale temp file: {temp_path}")

        _stream_download_to_temp(
            url=url,
            temp_path=temp_path,
            timeout_s=60.0,
            chunk_bytes=1024 * 1024,  # 1MB chunks
        )

        # 3) Atomic replace (final file appears only when download is complete)
        os.replace(str(temp_path), str(final_path))

    except Exception:
        # Best-effort cleanup of temp file
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                logger.warning(f"Failed to cleanup temp file: {temp_path}")
        logger.exception("Download failed")
        raise

    # 4) Final sanity check
    if not _is_valid_cached_file(final_path):
        raise RuntimeError("Download completed but file is missing or empty.")

    return str(final_path)
