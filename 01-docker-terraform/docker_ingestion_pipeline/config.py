# docker_ingestion_pipeline/config.py
from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from loguru import logger


# -----------------------------------------------------------------------------
# 1) Environment parsing helpers
# -----------------------------------------------------------------------------
# Why:
# - Keep env parsing rules consistent across the app (SRP).
# - Make config loading deterministic and easy to unit test.
#
# Tip for tests:
# - You can pass a custom env mapping (dict) instead of using os.environ directly.
# -----------------------------------------------------------------------------
def env_get(env: Mapping[str, str], name: str, default: str | None = None) -> str | None:
    """Return env[name] unless missing/empty, then return default."""
    raw = env.get(name)
    return raw if raw not in (None, "") else default


def env_bool(env: Mapping[str, str], name: str, default: bool = False) -> bool:
    """
    Parse a boolean environment variable.

    Truthy values (case-insensitive): 1, true, t, yes, y, on
    Falsy values  (case-insensitive): 0, false, f, no, n, off

    If missing/empty -> default.
    """
    raw = env_get(env, name)
    if raw is None:
        return default

    val = raw.strip().lower()
    if val in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if val in {"0", "false", "f", "no", "n", "off"}:
        return False

    # Fail fast: config errors should be explicit.
    raise ValueError(f"{name} must be boolean-like, got={raw!r}")


def env_int(env: Mapping[str, str], name: str, default: int, *, min_value: int = 1) -> int:
    """
    Parse an integer environment variable.

    If missing/empty -> default.
    Raises ValueError for non-integers or values below min_value.
    """
    raw = env_get(env, name)
    if raw is None:
        val = default
    else:
        try:
            val = int(raw)
        except ValueError as e:
            raise ValueError(f"{name} must be an integer, got={raw!r}") from e

    if val < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got={val}")
    return val


# -----------------------------------------------------------------------------
# 1b) Convenience wrappers for os.environ (public helpers)
# -----------------------------------------------------------------------------
# Why:
# - Keep call sites clean (no need to pass os.environ everywhere).
# - Preserve testability (env_* functions above remain pure / injectable).
# -----------------------------------------------------------------------------
def env_get_os(name: str, default: str | None = None) -> str | None:
    """Shortcut for env_get(os.environ, name, default)."""
    return env_get(os.environ, name, default)


def env_bool_os(name: str, default: bool = False) -> bool:
    """Shortcut for env_bool(os.environ, name, default)."""
    return env_bool(os.environ, name, default)


def env_int_os(name: str, default: int, *, min_value: int = 1) -> int:
    """Shortcut for env_int(os.environ, name, default, min_value=...)."""
    return env_int(os.environ, name, default, min_value=min_value)


# -----------------------------------------------------------------------------
# 2) Paths
# -----------------------------------------------------------------------------
def project_root() -> Path:
    """
    Return the absolute project root directory.

    Assumption:
    - This file lives at: <root>/docker_ingestion_pipeline/config.py
    - Therefore root is one directory above docker_ingestion_pipeline/
    """
    return Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Paths:
    """Immutable container of project directories used by the application."""

    base_dir: Path
    data_dir: Path
    log_dir: Path


def build_paths(env: Mapping[str, str] | None = None) -> Paths:
    """
    Resolve and create required directories.

    DATA_DIR:
    - If set, it can point outside the repo (useful in Docker volume mounts).
    - If not set, defaults to <project_root>/data.

    Note:
    - Directory creation is a side-effect. Keeping it here is OK because this is
      configuration/bootstrap code, not domain logic.
    """
    env = env or os.environ
    base = project_root()

    data_dir = Path(env_get(env, "DATA_DIR", str(base / "data")) or str(base / "data"))
    data_dir.mkdir(parents=True, exist_ok=True)

    log_dir = base / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    return Paths(base_dir=base, data_dir=data_dir, log_dir=log_dir)


# -----------------------------------------------------------------------------
# 3) Loader settings
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class LoaderSettings:
    """
    Loader batching/streaming settings.

    chunk_size:
      How many rows we read from the source file per iteration (I/O chunk).

    batch_size:
      How many rows we buffer before writing/flushing to the DB (DB batch).
    """

    chunk_size: int
    batch_size: int


def load_loader_settings(env: Mapping[str, str] | None = None) -> LoaderSettings:
    """
    Load loader settings from environment variables.

    LOADER_CHUNK_SIZE:
      number of rows per read chunk (streaming from file)

    LOADER_BATCH_SIZE:
      number of rows per DB flush/commit batch
    """
    env = env or os.environ
    return LoaderSettings(
        chunk_size=env_int(env, "LOADER_CHUNK_SIZE", 50_000, min_value=1),
        batch_size=env_int(env, "LOADER_BATCH_SIZE", 10_000, min_value=1),
    )


# -----------------------------------------------------------------------------
# 4) Logging
# -----------------------------------------------------------------------------
def _build_console_sink(*, enable_progress: bool) -> callable:
    """
    Build a console sink compatible with progress bars.

    Why:
    - tqdm writes progress bars on stdout/stderr.
    - Standard logging can corrupt the progress bar rendering.
    - Using tqdm.write(...) keeps progress output stable.
    """
    try:
        from tqdm import tqdm  # type: ignore
    except Exception:
        tqdm = None

    def _console_sink(message: str) -> None:
        if enable_progress and tqdm is not None:
            tqdm.write(message.rstrip("\n"))
        else:
            sys.stdout.write(message)
            sys.stdout.flush()

    return _console_sink


def configure_logging(paths: Paths, env: Mapping[str, str] | None = None) -> None:
    """
    Configure Loguru sinks (console + file).

    Console:
    - human-friendly formatting
    - tqdm-safe sink when ENABLE_PROGRESS=true

    File:
    - DEBUG level for richer debugging
    - log rotation/retention to prevent unbounded growth
    """
    env = env or os.environ
    logger.remove()

    log_level = env_get(env, "LOG_LEVEL", "INFO") or "INFO"
    enable_progress = env_bool(env, "ENABLE_PROGRESS", default=True)

    console_sink = _build_console_sink(enable_progress=enable_progress)

    logger.add(
        console_sink,
        level=log_level,
        colorize=True,
        backtrace=False,
        diagnose=False,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level}</level> | "
            "<level>{message}</level>\n"
        ),
    )

    logger.add(
        str(paths.log_dir / "app.log"),
        rotation="10 MB",
        retention="7 days",
        level="DEBUG",
        backtrace=False,
        diagnose=False,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
    )
