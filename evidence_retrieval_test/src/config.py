from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field


def _env_path() -> Path:
    return Path(__file__).resolve().parents[1] / ".env"


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _as_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _as_float(value: str | None, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _as_domains(value: str | None) -> list[str]:
    if not value:
        return _domains_from_default_catalog()
    return [domain.strip().lower() for domain in value.split(",") if domain.strip()]


def _domains_from_default_catalog() -> list[str]:
    catalog_path = Path(__file__).resolve().parent / "providers" / "crawl_sources.json"
    try:
        sources = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    domains: list[str] = []
    for source in sources:
        for domain in source.get("domains", []):
            clean_domain = str(domain).strip().lower()
            if clean_domain and clean_domain not in domains:
                domains.append(clean_domain)
    return domains


class EvidenceRetrievalSettings(BaseModel):
    ncbi_api_key: Optional[str] = None
    ncbi_tool_email: Optional[str] = None
    semantic_scholar_api_key: Optional[str] = None
    enable_semantic_scholar: bool = True
    enable_official_health_apis: bool = True
    enable_crawl4ai: bool = True
    enable_crawl4ai_browser: bool = False
    crawl_allowed_domains: list[str] = Field(default_factory=list)
    crawl_source_catalog_path: Optional[str] = None
    crawl_max_sources: int = 8
    crawl_max_pages: int = 14
    crawl_search_pages_per_source: int = 1
    crawl_time_budget_seconds: float = 8.0
    retrieval_time_budget_seconds: float = 10.0
    request_timeout_seconds: int = 20
    max_results_per_provider: int = 10


@lru_cache(maxsize=1)
def get_settings() -> EvidenceRetrievalSettings:
    load_dotenv(_env_path())
    load_dotenv()
    return EvidenceRetrievalSettings(
        ncbi_api_key=os.getenv("NCBI_API_KEY") or None,
        ncbi_tool_email=os.getenv("NCBI_TOOL_EMAIL") or None,
        semantic_scholar_api_key=os.getenv("SEMANTIC_SCHOLAR_API_KEY") or None,
        enable_semantic_scholar=_as_bool(os.getenv("ENABLE_SEMANTIC_SCHOLAR"), True),
        enable_official_health_apis=_as_bool(os.getenv("ENABLE_OFFICIAL_HEALTH_APIS"), True),
        enable_crawl4ai=_as_bool(os.getenv("ENABLE_CRAWL4AI"), True),
        enable_crawl4ai_browser=_as_bool(os.getenv("ENABLE_CRAWL4AI_BROWSER"), False),
        crawl_allowed_domains=_as_domains(os.getenv("CRAWL_ALLOWED_DOMAINS")),
        crawl_source_catalog_path=os.getenv("CRAWL_SOURCE_CATALOG_PATH") or None,
        crawl_max_sources=_as_int(os.getenv("CRAWL_MAX_SOURCES"), 8),
        crawl_max_pages=_as_int(os.getenv("CRAWL_MAX_PAGES"), 14),
        crawl_search_pages_per_source=_as_int(os.getenv("CRAWL_SEARCH_PAGES_PER_SOURCE"), 1),
        crawl_time_budget_seconds=_as_float(os.getenv("CRAWL_TIME_BUDGET_SECONDS"), 8.0),
        retrieval_time_budget_seconds=_as_float(os.getenv("RETRIEVAL_TIME_BUDGET_SECONDS"), 10.0),
        request_timeout_seconds=_as_int(os.getenv("REQUEST_TIMEOUT_SECONDS"), 20),
        max_results_per_provider=_as_int(os.getenv("MAX_RESULTS_PER_PROVIDER"), 10),
    )
