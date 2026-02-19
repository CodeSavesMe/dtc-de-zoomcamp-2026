# apps/download_to_gcs.py
from __future__ import annotations

import sys
from loguru import logger

from dw03.config.settings import AppSettings
from dw03.pipelines.gcs_ingest import DownloadToGcsPipeline
from dw03.runtime.setup_loging import setup_logging


def main() -> None:
    settings = AppSettings.from_env()
    setup_logging(settings.log_dir)

    try:
        pipeline = DownloadToGcsPipeline(settings)
        pipeline.run()
    except Exception as e:
        logger.exception("Download→GCS pipeline failed: {}", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
