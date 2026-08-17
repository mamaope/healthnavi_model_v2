from __future__ import annotations

import re
import time
from abc import ABC, abstractmethod

import httpx

from healthnavi.evidence_retrieval.config import EvidenceRetrievalSettings
from healthnavi.evidence_retrieval.models import EvidenceItem


class ProviderError(RuntimeError):
    """Raised when one evidence provider fails without stopping the whole search."""


class SimpleRateLimiter:
    def __init__(self, min_interval_seconds: float) -> None:
        self.min_interval_seconds = min_interval_seconds
        self._last_request_at = 0.0

    def wait(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        sleep_for = self.min_interval_seconds - elapsed
        if sleep_for > 0:
            time.sleep(sleep_for)
        self._last_request_at = time.monotonic()


class BaseEvidenceProvider(ABC):
    source_name: str

    def __init__(self, settings: EvidenceRetrievalSettings) -> None:
        self.settings = settings
        self.timeout = httpx.Timeout(settings.request_timeout_seconds)

    @abstractmethod
    def search(self, query: str, max_results: int) -> list[EvidenceItem]:
        """Return evidence items for a normalized clinical search query."""

    def _get_json(
        self,
        client: httpx.Client,
        url: str,
        params: dict[str, str | int | bool | None],
        headers: dict[str, str] | None = None,
    ) -> dict:
        clean_params = {key: value for key, value in params.items() if value is not None}
        for attempt in range(3):
            try:
                response = client.get(url, params=clean_params, headers=headers)
                response.raise_for_status()
                return response.json()
            except (httpx.TimeoutException, httpx.TransportError):
                if attempt == 2:
                    raise
                time.sleep(min(0.5 * (2**attempt), 4.0))
        raise ProviderError("HTTP JSON request failed")


def normalize_identifier(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().lower().replace("https://doi.org/", "")


def normalize_title(title: str) -> str:
    lowered = title.lower()
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()
