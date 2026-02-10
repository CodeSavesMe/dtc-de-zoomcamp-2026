# dw03/adapters/gcs_client.py

from __future__ import annotations

from google.cloud import storage

class GCSStorage:
    def __init__(self) -> None:
        self._client = storage.Client()

    def get_bucket(self, bucket_name: str) -> storage.Bucket:
        return self._client.bucket(bucket_name)
