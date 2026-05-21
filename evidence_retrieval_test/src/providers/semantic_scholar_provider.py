from __future__ import annotations

import threading
import time

import httpx

from evidence_retrieval_test.src.config import EvidenceRetrievalSettings
from evidence_retrieval_test.src.models import EvidenceItem, EvidenceSource
from evidence_retrieval_test.src.providers.base import BaseEvidenceProvider, ProviderError


SEMANTIC_SCHOLAR_MIN_INTERVAL_SECONDS = 1.15


class _SemanticScholarRateLimiter:
    def __init__(self, min_interval_seconds: float) -> None:
        self.min_interval_seconds = min_interval_seconds
        self._last_request_at = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            elapsed = time.monotonic() - self._last_request_at
            sleep_for = self.min_interval_seconds - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)
            self._last_request_at = time.monotonic()


_SEMANTIC_SCHOLAR_RATE_LIMITER = _SemanticScholarRateLimiter(
    SEMANTIC_SCHOLAR_MIN_INTERVAL_SECONDS
)


class SemanticScholarProvider(BaseEvidenceProvider):
    source_name = EvidenceSource.SEMANTIC_SCHOLAR.value
    SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

    def __init__(self, settings: EvidenceRetrievalSettings) -> None:
        super().__init__(settings)

    def search(self, query: str, max_results: int) -> list[EvidenceItem]:
        if not self.settings.enable_semantic_scholar:
            return []

        for search_query in _query_candidates(query):
            results = self._search_results(search_query, max_results)
            if results:
                return [
                    self._paper_to_item(paper, original_query=query, query_used=search_query)
                    for paper in results
                ]
        return []

    def _search_results(self, query: str, max_results: int) -> list[dict]:

        fields = ",".join(
            [
                "title",
                "abstract",
                "authors",
                "year",
                "venue",
                "citationCount",
                "influentialCitationCount",
                "externalIds",
                "openAccessPdf",
                "url",
            ]
        )
        params = {"query": query, "limit": max_results, "fields": fields}
        headers = _semantic_scholar_headers(self.settings.semantic_scholar_api_key)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                _SEMANTIC_SCHOLAR_RATE_LIMITER.wait()
                data = self._get_json(client, self.SEARCH_URL, params, headers=headers)
        except httpx.HTTPError as exc:
            raise ProviderError(f"Semantic Scholar search failed: {exc}") from exc
        return data.get("data", [])

    def _paper_to_item(
        self,
        paper: dict,
        *,
        original_query: str | None = None,
        query_used: str | None = None,
    ) -> EvidenceItem:
        external = paper.get("externalIds") or {}
        open_pdf = paper.get("openAccessPdf") or {}
        paper_id = paper.get("paperId") or external.get("DOI") or paper.get("title")
        return EvidenceItem(
            id=f"semantic_scholar:{paper_id}",
            source=EvidenceSource.SEMANTIC_SCHOLAR,
            title=paper.get("title") or "Untitled paper",
            abstract=paper.get("abstract"),
            authors=[author.get("name") for author in paper.get("authors", []) if author.get("name")],
            journal_or_publisher=paper.get("venue"),
            year=paper.get("year"),
            doi=external.get("DOI"),
            pmid=external.get("PubMed"),
            pmcid=external.get("PubMedCentral"),
            url=paper.get("url") or "https://www.semanticscholar.org/",
            full_text_url=open_pdf.get("url"),
            open_access=bool(open_pdf.get("url")),
            citation_count=paper.get("citationCount"),
            evidence_type=_evidence_type(paper),
            raw={
                "influential_citation_count": paper.get("influentialCitationCount"),
                "external_ids": external,
                "original_query": original_query,
                "query_used": query_used,
            },
        )


def _semantic_scholar_headers(api_key: str | None) -> dict[str, str]:
    if not api_key:
        return {}
    return {"x-api-key": api_key}


def _evidence_type(paper: dict) -> str:
    haystack = " ".join(str(paper.get(key, "")) for key in ("title", "abstract")).lower()
    if "guideline" in haystack:
        return "guideline"
    if "systematic review" in haystack or "meta-analysis" in haystack:
        return "systematic_review"
    if "randomized" in haystack or "clinical trial" in haystack:
        return "clinical_trial"
    if "review" in haystack:
        return "review"
    return "journal_article"


def _query_candidates(query: str) -> list[str]:
    candidates: list[str] = []
    _append_unique(candidates, query.strip())
    _append_unique(candidates, _query_token_and_search(query))
    return candidates


def _query_token_and_search(query: str) -> str:
    tokens = _query_tokens(query)
    if not tokens:
        return query
    return " ".join(tokens)


def _query_tokens(query: str) -> list[str]:
    import re

    seen: set[str] = set()
    tokens: list[str] = []
    for token in re.sub(r"[^a-zA-Z0-9\s]", " ", query.lower()).split():
        if token.isdigit() or len(token) < 3 or token in _NON_CONTENT_QUERY_TERMS or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def _append_unique(values: list[str], value: str | None) -> None:
    if value and value not in values:
        values.append(value)


_NON_CONTENT_QUERY_TERMS = {
    "about",
    "after",
    "and",
    "best",
    "can",
    "care",
    "clinical",
    "does",
    "for",
    "from",
    "guidance",
    "guideline",
    "guidelines",
    "have",
    "help",
    "how",
    "in",
    "manage",
    "management",
    "old",
    "of",
    "on",
    "or",
    "patient",
    "patients",
    "should",
    "the",
    "to",
    "therapy",
    "treat",
    "treatment",
    "using",
    "what",
    "when",
    "with",
    "year",
    "years",
}
