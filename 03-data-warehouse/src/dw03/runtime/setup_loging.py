# src/dw03/runtime/setup_loging.py
from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger


def setup_logging(log_dir: str) -> None:
    """
    Setup Loguru logger:
    - stdout logger (for terminal)
    - file logger (logs/app.log)
    """
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    logger.remove()

    logger.add(
        sys.stdout,
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        backtrace=False,
        diagnose=False,
    )

    logger.add(
        log_path / "app.log",
        rotation="10 MB",
        retention="14 days",
        compression="zip",
        level="INFO",
        backtrace=False,
        diagnose=False,
    )
