# src/dw03/adapters/bq_client.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from google.cloud import bigquery
from loguru import logger


@dataclass
class BigQueryClient:
    project_id: str
    location: str
    labels: Optional[dict[str, str]] = None

    def __post_init__(self) -> None:
        """Initialize the BigQuery client."""
        self._client: bigquery.Client = bigquery.Client(
            project=self.project_id,
            location=self.location,
        )

    @property
    def raw(self) -> bigquery.Client:
        """Access the underlying BigQuery client."""
        return self._client

    def dry_run(self, sql: str) -> int:
        """Estimate query cost by returning total bytes processed."""
        job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
        if self.labels:
            job_config.labels = self.labels

        job = self._client.query(sql, job_config=job_config)
        return int(job.total_bytes_processed or 0)

    def execute_job(self, sql: str) -> bigquery.QueryJob:
        """
        Execute a query and wait for completion.
        Returns the full QueryJob object to allow row fetching.
        """
        job_config = bigquery.QueryJobConfig()
        if self.labels:
            job_config.labels = self.labels

        job = self._client.query(sql, job_config=job_config)
        logger.info("Waiting BigQuery job... (location={})", self.location)
        job.result()
        return job

    def execute(self, sql: str) -> str:
        """Execute query and return only the job_id (Backward compatibility)."""
        job = self.execute_job(sql)
        return job.job_id