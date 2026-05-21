from __future__ import annotations

import math
import re
from datetime import date

from evidence_retrieval_test.src.models import EvidenceItem
from evidence_retrieval_test.src.providers.base import normalize_identifier, normalize_title


REPUTABLE_SOURCE_BONUS = {
    "pubmed": 0.12,
    "europe_pmc": 0.12,
    "semantic_scholar": 0.04,
    "official_health_api": 0.12,
    "crawl4ai": 0.10,
}

REPUTABLE_DOMAINS = {
    "nih.gov",
    "clinicalinfo.hiv.gov",
    "who.int",
    "wkc.who.int",
    "pmnch.who.int",
    "cdc.gov",
    "idsociety.org",
    "health.go.ug",
    "differentiatedservicedelivery.org",
    "cphl.go.ug",
    "iris.who.int",
    "stacks.cdc.gov",
    "ncbi.nlm.nih.gov",
    "medicalguidelines.msf.org",
    "unicef.org",
    "reliefweb.int",
    "platform.who.int",
    "nice.org.uk",
    "ecdc.europa.eu",
    "africacdc.org",
    "ghoapi.azureedge.net",
    "api.worldbank.org",
    "worldbank.org",
    "unaids.org",
    "paho.org",
    "aafp.org",
    "europepmc.org",
    "pubmed.ncbi.nlm.nih.gov",
}

LOCAL_PRIORITY_DOMAINS = {
    "health.go.ug",
    "library.health.go.ug",
    "cphl.go.ug",
    "africacdc.org",
}

REGIONAL_PRIORITY_DOMAINS = {
    "who.int",
    "afro.who.int",
    "iris.who.int",
    "ghoapi.azureedge.net",
    "api.worldbank.org",
    "worldbank.org",
    "unaids.org",
    "unicef.org",
    "reliefweb.int",
}

LOCAL_PRIORITY_TERMS = {
    "uganda",
    "ugandan",
    "zambia",
    "zambian",
    "africa",
    "african",
    "sub-saharan",
    "sub saharan",
}

EVIDENCE_TYPE_BONUS = {
    "guideline": 0.30,
    "systematic_review": 0.24,
    "clinical_trial": 0.20,
    "review": 0.12,
    "clinical_resource": 0.08,
    "official_guidance": 0.18,
    "official_indicator": 0.14,
    "journal_article": 0.05,
}


def rank_evidence_items(query: str, items: list[EvidenceItem]) -> list[EvidenceItem]:
    scored = [score_evidence_item(query, item) for item in items]
    return sorted(scored, key=lambda item: item.final_score or 0.0, reverse=True)


def score_evidence_item(query: str, item: EvidenceItem) -> EvidenceItem:
    scoring_query = _query_for_item(query, item)
    relevance = keyword_overlap_score(
        scoring_query,
        " ".join(part for part in [item.title, item.abstract or "", item.snippet or ""] if part),
    )
    credibility = _credibility_score(item)
    recency = _recency_score(item.year)
    open_access = 0.08 if item.open_access or item.full_text_url else 0.0
    citation_signal = _citation_score(item.citation_count)
    local_signal = _local_priority_score(item)
    missing_abstract_penalty = -0.08 if not item.abstract and not item.snippet else 0.0
    weak_title_penalty = -0.08 if keyword_overlap_score(scoring_query, item.title) < 0.08 else 0.0

    final_score = (
        0.38 * relevance
        + credibility
        + recency
        + open_access
        + citation_signal
        + local_signal
        + missing_abstract_penalty
        + weak_title_penalty
    )
    item.relevance_score = round(relevance, 4)
    item.credibility_score = round(credibility, 4)
    item.final_score = round(max(final_score, 0.0), 4)
    return item


def _query_for_item(query: str, item: EvidenceItem) -> str:
    if isinstance(item.raw, dict):
        query_used = item.raw.get("query_used")
        if isinstance(query_used, str) and query_used.strip():
            return f"{query} {query_used.strip()}"
    return query


def deduplicate_items(items: list[EvidenceItem]) -> list[EvidenceItem]:
    seen: set[str] = set()
    deduped: list[EvidenceItem] = []
    for item in items:
        keys = [
            f"doi:{normalize_identifier(item.doi)}" if item.doi else None,
            f"pmid:{normalize_identifier(item.pmid)}" if item.pmid else None,
            f"pmcid:{normalize_identifier(item.pmcid)}" if item.pmcid else None,
            f"title:{normalize_title(item.title)}" if item.title else None,
        ]
        if any(key in seen for key in keys if key):
            continue
        for key in keys:
            if key:
                seen.add(key)
        deduped.append(item)
    return deduped


def keyword_overlap_score(query: str, text: str) -> float:
    query_tokens = _tokens(query)
    text_tokens = _tokens(text)
    if not query_tokens or not text_tokens:
        return 0.0
    overlap = query_tokens.intersection(text_tokens)
    return min(len(overlap) / math.sqrt(len(query_tokens) * len(text_tokens)), 1.0)


def _tokens(value: str) -> set[str]:
    stopwords = {"the", "and", "for", "with", "from", "this", "that", "into", "what"}
    return {
        token
        for token in re.sub(r"[^a-zA-Z0-9\s]", " ", value.lower()).split()
        if len(token) > 2 and token not in stopwords
    }


def _credibility_score(item: EvidenceItem) -> float:
    source_key = getattr(item.source, "value", str(item.source))
    score = REPUTABLE_SOURCE_BONUS.get(source_key, 0.02)
    score += EVIDENCE_TYPE_BONUS.get(item.evidence_type or "", 0.0)
    url = str(item.url).lower()
    if any(domain in url for domain in REPUTABLE_DOMAINS):
        score += 0.10
    return min(score, 0.55)


def _local_priority_score(item: EvidenceItem) -> float:
    url = str(item.url).lower()
    text = " ".join(
        part
        for part in (
            item.title,
            item.abstract or "",
            item.snippet or "",
            item.journal_or_publisher or "",
        )
        if part
    ).lower()

    score = 0.0
    if any(domain in url for domain in LOCAL_PRIORITY_DOMAINS):
        score += 0.22
    elif any(domain in url for domain in REGIONAL_PRIORITY_DOMAINS):
        score += 0.10

    if any(term in text for term in LOCAL_PRIORITY_TERMS):
        score += 0.10
    return min(score, 0.28)


def _recency_score(year: int | None) -> float:
    if not year:
        return 0.0
    age = date.today().year - year
    if age <= 2:
        return 0.16
    if age <= 5:
        return 0.12
    if age <= 10:
        return 0.06
    if age <= 20:
        return 0.01
    return -0.05


def _citation_score(citation_count: int | None) -> float:
    if not citation_count:
        return 0.0
    return min(math.log10(citation_count + 1) / 20, 0.12)
