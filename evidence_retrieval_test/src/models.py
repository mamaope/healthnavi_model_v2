from __future__ import annotations

from enum import Enum
from typing import Any, Optional, Union

from pydantic import BaseModel, Field, HttpUrl


class EvidenceSource(str, Enum):
    PUBMED = "pubmed"
    EUROPE_PMC = "europe_pmc"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    OFFICIAL_HEALTH_API = "official_health_api"
    CRAWL4AI = "crawl4ai"


class EvidenceItem(BaseModel):
    id: str
    source: Union[EvidenceSource, str]
    title: str
    abstract: Optional[str] = None
    snippet: Optional[str] = None
    authors: list[str] = Field(default_factory=list)
    journal_or_publisher: Optional[str] = None
    publication_date: Optional[str] = None
    year: Optional[int] = None
    doi: Optional[str] = None
    pmid: Optional[str] = None
    pmcid: Optional[str] = None
    url: Union[HttpUrl, str]
    full_text_url: Optional[Union[HttpUrl, str]] = None
    open_access: Optional[bool] = None
    citation_count: Optional[int] = None
    evidence_type: Optional[str] = None
    relevance_score: Optional[float] = None
    credibility_score: Optional[float] = None
    final_score: Optional[float] = None
    raw: Optional[dict[str, Any]] = None


class SearchResult(BaseModel):
    query: str
    normalized_query: str
    total_results: int
    items: list[EvidenceItem] = Field(default_factory=list)
    provider_errors: list[str] = Field(default_factory=list)
    timings_ms: dict[str, float] = Field(default_factory=dict)
