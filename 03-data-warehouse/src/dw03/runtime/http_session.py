# src/dw03/runtime/http_session.py

from __future__ import annotations

import threading
from typing import Optional

import requests
from requests.adapters import HTTPAdapter


class PerThreadHttpSession:
    """
    One requests.Session per thread.

    Important:
    - internal retries are disabled (max_retries=0)
    - retry is handled by our own retry loop for clearer logs and control
    """

    def __init__(self, pool_size: int = 2) -> None:
        self._pool_size = pool_size
        self._local = threading.local()

    def get(self) -> requests.Session:
        existing: Optional[requests.Session] = getattr(self._local, "session", None)
        if existing is not None:
            return existing

        session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=self._pool_size,
            pool_maxsize=self._pool_size,
            max_retries=0,  # disable internal retries
        )
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        self._local.session = session
        return session
