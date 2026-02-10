# src/dw03/adapters/bq_client.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from google.cloud import bigquery
from loguru import logger


@dataclass
class BigQueryClient:
    """
    Beginner-friendly wrapper for google-cloud-bigquery Client.

    - dry_run(sql)  -> returns estimated bytes scanned
    - execute(sql)  -> runs query and returns job_id
    """
    project_id: str
    location: str
    labels: Optional[dict[str, str]] = None

    def __post_init__(self) -> None:
        self._client: bigquery.Client = bigquery.Client(
            project=self.project_id,
            location=self.location,
        )

    @property
    def raw(self) -> bigquery.Client:
        """Expose underlying SDK client when needed."""
        return self._client

    def dry_run(self, sql: str) -> int:
        job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
        if self.labels:
            job_config.labels = self.labels

        job = self._client.query(sql, job_config=job_config)
        return int(job.total_bytes_processed or 0)

    def execute(self, sql: str) -> str:
        job_config = bigquery.QueryJobConfig()
        if self.labels:
            job_config.labels = self.labels

        job = self._client.query(sql, job_config=job_config)
        logger.info("Waiting BigQuery job... (location={})", self.location)
        job.result()
        return job.job_id
