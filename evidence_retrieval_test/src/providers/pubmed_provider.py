from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from evidence_retrieval_test.src.config import EvidenceRetrievalSettings
from evidence_retrieval_test.src.models import EvidenceItem, EvidenceSource
from evidence_retrieval_test.src.providers.base import (
    BaseEvidenceProvider,
    ProviderError,
    SimpleRateLimiter,
)


class PubMedProvider(BaseEvidenceProvider):
    source_name = EvidenceSource.PUBMED.value
    ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    ESPELL_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/espell.fcgi"

    def __init__(self, settings: EvidenceRetrievalSettings) -> None:
        super().__init__(settings)
        interval = 0.10 if settings.ncbi_api_key else 0.34
        self.rate_limiter = SimpleRateLimiter(interval)

    def search(self, query: str, max_results: int) -> list[EvidenceItem]:
        for search_query in self._query_candidates(query):
            pmids = self._search_pmids(search_query, max_results)
            if pmids:
                return self.fetch_details(pmids, original_query=query, query_used=search_query)
        return []

    def _base_params(self) -> dict[str, str | None]:
        return {
            "tool": "empirico_evidence_retrieval_test",
            "email": self.settings.ncbi_tool_email,
            "api_key": self.settings.ncbi_api_key,
        }

    def _search_pmids(self, query: str, max_results: int) -> list[str]:
        params = {
            **self._base_params(),
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": max_results,
            "sort": "relevance",
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                self.rate_limiter.wait()
                data = self._get_json(client, self.ESEARCH_URL, params)
        except httpx.HTTPError as exc:
            raise ProviderError(f"PubMed ESearch failed: {exc}") from exc
        return data.get("esearchresult", {}).get("idlist", [])

    def _query_candidates(self, query: str) -> list[str]:
        candidates: list[str] = []
        _append_unique(candidates, query.strip())

        corrected_query = self._correct_spelling(query)
        if corrected_query:
            _append_unique(candidates, corrected_query)

        for candidate in list(candidates):
            _append_unique(candidates, _query_token_and_search(candidate))

        return candidates

    def _correct_spelling(self, query: str) -> str | None:
        params = {
            **self._base_params(),
            "db": "pubmed",
            "term": query,
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                self.rate_limiter.wait()
                response = client.get(
                    self.ESPELL_URL,
                    params={key: value for key, value in params.items() if value is not None},
                )
                response.raise_for_status()
        except httpx.HTTPError:
            return None
        return _parse_corrected_query(response.text)

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError)),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _get_xml(self, client: httpx.Client, pmids: list[str]) -> str:
        params = {
            **self._base_params(),
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
        }
        response = client.get(
            self.EFETCH_URL,
            params={key: value for key, value in params.items() if value is not None},
        )
        response.raise_for_status()
        return response.text

    def fetch_details(
        self,
        pmids: list[str],
        *,
        original_query: str | None = None,
        query_used: str | None = None,
    ) -> list[EvidenceItem]:
        try:
            with httpx.Client(timeout=self.timeout) as client:
                self.rate_limiter.wait()
                xml_text = self._get_xml(client, pmids)
        except httpx.HTTPError as exc:
            raise ProviderError(f"PubMed EFetch failed: {exc}") from exc

        root = ET.fromstring(xml_text)
        return [
            item
            for article in root.findall(".//PubmedArticle")
            if (item := self._article_to_item(article, original_query, query_used)) is not None
        ]

    def _article_to_item(
        self,
        article: ET.Element,
        original_query: str | None = None,
        query_used: str | None = None,
    ) -> EvidenceItem | None:
        pmid = _text(article.find(".//MedlineCitation/PMID"))
        title = _text(article.find(".//ArticleTitle"))
        if not pmid or not title:
            return None

        abstract_parts = []
        for node in article.findall(".//Abstract/AbstractText"):
            label = node.attrib.get("Label")
            text = "".join(node.itertext()).strip()
            if text and label:
                abstract_parts.append(f"{label}: {text}")
            elif text:
                abstract_parts.append(text)

        authors = []
        for author in article.findall(".//AuthorList/Author"):
            last = _text(author.find("LastName"))
            fore = _text(author.find("ForeName")) or _text(author.find("Initials"))
            collective = _text(author.find("CollectiveName"))
            if collective:
                authors.append(collective)
            elif last and fore:
                authors.append(f"{fore} {last}")
            elif last:
                authors.append(last)

        article_ids = {
            node.attrib.get("IdType", "").lower(): (node.text or "").strip()
            for node in article.findall(".//PubmedData/ArticleIdList/ArticleId")
            if node.text
        }
        publication_types = [
            (node.text or "").strip()
            for node in article.findall(".//PublicationTypeList/PublicationType")
            if node.text
        ]

        return EvidenceItem(
            id=f"pubmed:{pmid}",
            source=EvidenceSource.PUBMED,
            title=title,
            abstract="\n".join(abstract_parts) or None,
            authors=authors,
            journal_or_publisher=_text(article.find(".//Journal/Title")),
            publication_date=_publication_date(article),
            year=_publication_year(article),
            doi=article_ids.get("doi"),
            pmid=pmid,
            pmcid=article_ids.get("pmc"),
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            evidence_type=_evidence_type(publication_types, title, "\n".join(abstract_parts)),
            raw={
                "publication_types": publication_types,
                "original_query": original_query,
                "query_used": query_used,
            },
        )


def _text(node: ET.Element | None) -> str | None:
    if node is None:
        return None
    value = "".join(node.itertext()).strip()
    return value or None


def _publication_year(article: ET.Element) -> int | None:
    for path in (
        ".//ArticleDate/Year",
        ".//JournalIssue/PubDate/Year",
        ".//MedlineDate",
    ):
        value = _text(article.find(path))
        if value and value[:4].isdigit():
            return int(value[:4])
    return None


def _publication_date(article: ET.Element) -> str | None:
    year = _text(article.find(".//ArticleDate/Year")) or _text(
        article.find(".//JournalIssue/PubDate/Year")
    )
    month = _text(article.find(".//ArticleDate/Month")) or _text(
        article.find(".//JournalIssue/PubDate/Month")
    )
    day = _text(article.find(".//ArticleDate/Day")) or _text(
        article.find(".//JournalIssue/PubDate/Day")
    )
    if not year:
        medline_date = _text(article.find(".//MedlineDate"))
        return medline_date
    return "-".join(part for part in (year, month, day) if part)


def _evidence_type(publication_types: list[str], title: str, abstract: str) -> str:
    haystack = " ".join(publication_types + [title, abstract]).lower()
    if "practice guideline" in haystack or "guideline" in haystack:
        return "guideline"
    if "systematic review" in haystack or "meta-analysis" in haystack:
        return "systematic_review"
    if "randomized" in haystack or "clinical trial" in haystack:
        return "clinical_trial"
    if "review" in haystack:
        return "review"
    return "journal_article"


def _query_token_and_search(query: str) -> str:
    tokens = _query_tokens(query)
    if not tokens:
        return query
    return " AND ".join(tokens)


def _query_tokens(query: str) -> list[str]:
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


def _parse_corrected_query(xml_text: str) -> str | None:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    corrected = _text(root.find(".//CorrectedQuery"))
    return corrected if corrected else None


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
