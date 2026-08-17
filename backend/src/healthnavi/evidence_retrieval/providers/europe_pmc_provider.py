from __future__ import annotations

import re

import httpx

from healthnavi.evidence_retrieval.config import EvidenceRetrievalSettings
from healthnavi.evidence_retrieval.models import EvidenceItem, EvidenceSource
from healthnavi.evidence_retrieval.providers.base import BaseEvidenceProvider, ProviderError


class EuropePMCProvider(BaseEvidenceProvider):
    source_name = EvidenceSource.EUROPE_PMC.value
    SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

    def __init__(self, settings: EvidenceRetrievalSettings) -> None:
        super().__init__(settings)

    def search(self, query: str, max_results: int) -> list[EvidenceItem]:
        for search_query in _query_candidates(query):
            results = self._search_results(search_query, max_results)
            if results:
                return [
                    self._result_to_item(result, original_query=query, query_used=search_query)
                    for result in results
                    if result.get("title")
                ]
        return []

    def _search_results(self, query: str, max_results: int) -> list[dict]:
        escaped_query = _escape_query(query)
        params = {
            "query": f"(TITLE:({escaped_query}) OR ABSTRACT:({escaped_query})) AND (SRC:MED OR SRC:PMC)",
            "format": "json",
            "resultType": "core",
            "pageSize": max_results,
            "sort": "RELEVANCE",
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                data = self._get_json(client, self.SEARCH_URL, params)
        except httpx.HTTPError as exc:
            raise ProviderError(f"Europe PMC search failed: {exc}") from exc
        return data.get("resultList", {}).get("result", [])

    def _result_to_item(
        self,
        result: dict,
        *,
        original_query: str | None = None,
        query_used: str | None = None,
    ) -> EvidenceItem:
        pmid = result.get("pmid")
        pmcid = result.get("pmcid")
        doi = result.get("doi")
        source = result.get("source") or "MED"
        identifier = pmcid or pmid or doi or result.get("id")
        full_text_url = _full_text_url(result)
        url = _article_url(source, identifier, doi)

        return EvidenceItem(
            id=f"europe_pmc:{identifier}",
            source=EvidenceSource.EUROPE_PMC,
            title=result.get("title", "").strip(),
            abstract=result.get("abstractText"),
            authors=_authors(result.get("authorString")),
            journal_or_publisher=result.get("journalTitle"),
            publication_date=result.get("firstPublicationDate") or result.get("pubYear"),
            year=_safe_year(result.get("pubYear") or result.get("firstPublicationDate")),
            doi=doi,
            pmid=pmid,
            pmcid=pmcid,
            url=url,
            full_text_url=full_text_url,
            open_access=_as_bool(result.get("isOpenAccess")) or bool(full_text_url),
            citation_count=_safe_int(result.get("citedByCount")),
            evidence_type="journal_article",
            raw={
                **result,
                "original_query": original_query,
                "query_used": query_used,
            },
        )


def _escape_query(query: str) -> str:
    return query.replace('"', " ").strip()


def _query_candidates(query: str) -> list[str]:
    candidates: list[str] = []
    _append_unique(candidates, query.strip())
    _append_unique(candidates, _query_token_and_search(query))
    return candidates


def _query_token_and_search(query: str) -> str:
    tokens = _query_tokens(query)
    if not tokens:
        return query
    return " AND ".join(tokens)


def _query_tokens(query: str) -> list[str]:
    seen: set[str] = set()
    tokens: list[str] = []
    for token in re.sub(r"[^a-zA-Z0-9\s]", " ", query.lower()).split():
        if token.isdigit() or len(token) < 3 or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def _append_unique(values: list[str], value: str | None) -> None:
    if value and value not in values:
        values.append(value)


def _article_url(source: str, identifier: str | None, doi: str | None) -> str:
    if identifier:
        return f"https://europepmc.org/article/{source}/{identifier}"
    if doi:
        return f"https://doi.org/{doi}"
    return "https://europepmc.org/"


def _full_text_url(result: dict) -> str | None:
    urls = (
        result.get("fullTextUrlList", {}).get("fullTextUrl")
        if isinstance(result.get("fullTextUrlList"), dict)
        else None
    )
    if not urls:
        return None
    for item in urls:
        if item.get("availability", "").lower() in {"open access", "free"}:
            return item.get("url")
    return urls[0].get("url")


def _authors(author_string: str | None) -> list[str]:
    if not author_string:
        return []
    return [author.strip() for author in author_string.split(",") if author.strip()]


def _safe_year(value: str | int | None) -> int | None:
    if value is None:
        return None
    text = str(value)
    return int(text[:4]) if text[:4].isdigit() else None


def _safe_int(value: str | int | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_bool(value: str | bool | None) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    return str(value).lower() in {"y", "yes", "true", "1"}

