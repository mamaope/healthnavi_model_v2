from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field


def _env_paths() -> list[Path]:
    backend_dir = Path(__file__).resolve().parents[3]
    project_dir = backend_dir.parent
    return [
        project_dir / ".env",
        backend_dir / ".env.local",
        backend_dir / ".env.production",
        backend_dir / ".env",
    ]


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


def _as_csv(value: str | None, default: list[str]) -> list[str]:
    if not value:
        return default
    values = [item.strip().upper() for item in value.split(",") if item.strip()]
    return values or default


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
    deployment_country: Optional[str] = None
    ncbi_api_key: Optional[str] = None
    ncbi_tool_email: Optional[str] = None
    semantic_scholar_api_key: Optional[str] = None
    enable_pubmed: bool = True
    enable_europe_pmc: bool = True
    enable_semantic_scholar: bool = True
    enable_official_health_apis: bool = True
    official_health_api_country_codes: list[str] = Field(default_factory=lambda: ["UGA"])
    enable_crawl4ai: bool = True
    enable_crawl4ai_browser: bool = False
    crawl_allowed_domains: list[str] = Field(default_factory=list)
    crawl_source_catalog_path: Optional[str] = None
    crawl_cache_dir: Optional[str] = None
    crawl_cache_ttl_seconds: int = 604800
    crawl_max_sources: int = 8
    crawl_max_pages: int = 14
    crawl_search_pages_per_source: int = 1
    crawl_time_budget_seconds: float = 14.0
    retrieval_time_budget_seconds: float = 18.0
    request_timeout_seconds: int = 20
    max_results_per_provider: int = 10


@lru_cache(maxsize=1)
def get_settings() -> EvidenceRetrievalSettings:
    for env_path in _env_paths():
        if env_path.exists():
            load_dotenv(env_path, override=False)
    load_dotenv(override=False)
    return EvidenceRetrievalSettings(
        deployment_country=(
            os.getenv("DEPLOYMENT_COUNTRY")
            or os.getenv("COUNTRY_CODE")
            or os.getenv("CLINICAL_AI_COUNTRY_CODE")
            or None
        ),
        ncbi_api_key=os.getenv("NCBI_API_KEY") or None,
        ncbi_tool_email=os.getenv("NCBI_TOOL_EMAIL") or None,
        semantic_scholar_api_key=os.getenv("SEMANTIC_SCHOLAR_API_KEY") or None,
        enable_pubmed=_as_bool(os.getenv("ENABLE_PUBMED"), True),
        enable_europe_pmc=_as_bool(os.getenv("ENABLE_EUROPE_PMC"), True),
        enable_semantic_scholar=_as_bool(os.getenv("ENABLE_SEMANTIC_SCHOLAR"), True),
        enable_official_health_apis=_as_bool(os.getenv("ENABLE_OFFICIAL_HEALTH_APIS"), True),
        official_health_api_country_codes=_as_csv(
            os.getenv("OFFICIAL_HEALTH_API_COUNTRY_CODES"),
            ["UGA"],
        ),
        enable_crawl4ai=_as_bool(os.getenv("ENABLE_CRAWL4AI"), True),
        enable_crawl4ai_browser=_as_bool(os.getenv("ENABLE_CRAWL4AI_BROWSER"), False),
        crawl_allowed_domains=_as_domains(os.getenv("CRAWL_ALLOWED_DOMAINS")),
        crawl_source_catalog_path=os.getenv("CRAWL_SOURCE_CATALOG_PATH") or None,
        crawl_cache_dir=os.getenv("CRAWL_CACHE_DIR") or None,
        crawl_cache_ttl_seconds=_as_int(os.getenv("CRAWL_CACHE_TTL_SECONDS"), 604800),
        crawl_max_sources=_as_int(os.getenv("CRAWL_MAX_SOURCES"), 8),
        crawl_max_pages=_as_int(os.getenv("CRAWL_MAX_PAGES"), 14),
        crawl_search_pages_per_source=_as_int(os.getenv("CRAWL_SEARCH_PAGES_PER_SOURCE"), 1),
        crawl_time_budget_seconds=_as_float(os.getenv("CRAWL_TIME_BUDGET_SECONDS"), 14.0),
        retrieval_time_budget_seconds=_as_float(os.getenv("RETRIEVAL_TIME_BUDGET_SECONDS"), 18.0),
        request_timeout_seconds=_as_int(os.getenv("REQUEST_TIMEOUT_SECONDS"), 20),
        max_results_per_provider=_as_int(os.getenv("MAX_RESULTS_PER_PROVIDER"), 10),
    )
