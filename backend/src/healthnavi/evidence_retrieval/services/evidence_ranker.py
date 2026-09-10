from __future__ import annotations

import math
import re
from datetime import date

from healthnavi.evidence_retrieval.models import EvidenceItem
from healthnavi.evidence_retrieval.providers.base import normalize_identifier, normalize_title
from healthnavi.evidence_retrieval.services.evidence_policy import (
    evidence_type_bonus,
    source_trust_bonus,
)


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
    "dailymed.nlm.nih.gov",
    "medicalguidelines.msf.org",
    "unicef.org",
    "reliefweb.int",
    "platform.who.int",
    "nice.org.uk",
    "cks.nice.org.uk",
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
    "ginasthma.org",
    "goldcopd.org",
    "kdigo.org",
    "escardio.org",
    "acog.org",
    "rcog.org.uk",
    "worldgastroenterology.org",
}

EVIDENCE_TYPE_BONUS = {
    "guideline": 0.08,
    "systematic_review": 0.06,
    "clinical_trial": 0.05,
    "review": 0.03,
    "clinical_resource": 0.04,
    "official_guidance": 0.06,
    "official_indicator": 0.03,
    "journal_article": 0.01,
}


def rank_evidence_items(query: str, items: list[EvidenceItem]) -> list[EvidenceItem]:
    scored = [score_evidence_item(query, item) for item in items]
    return sorted(scored, key=lambda item: item.final_score or 0.0, reverse=True)


def score_evidence_item(query: str, item: EvidenceItem) -> EvidenceItem:
    scoring_query = _query_for_item(query, item)
    relevance = lexical_overlap_score(
        scoring_query,
        " ".join(part for part in [item.title, item.abstract or "", item.snippet or ""] if part),
    )
    credibility = _credibility_score(item)
    recency = _recency_score(item.year)
    open_access = 0.08 if item.open_access or item.full_text_url else 0.0
    citation_signal = _citation_score(item.citation_count)
    missing_abstract_penalty = -0.08 if not item.abstract and not item.snippet else 0.0
    weak_title_penalty = -0.08 if lexical_overlap_score(scoring_query, item.title) < 0.08 else 0.0

    final_score = (
        0.38 * relevance
        + credibility
        + recency
        + open_access
        + citation_signal
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
        key = _passage_dedupe_key(item)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _passage_dedupe_key(item: EvidenceItem) -> str:
    document_key = _document_dedupe_key(item)
    raw = item.raw if isinstance(item.raw, dict) else {}
    section = _normalize_dedupe_text(
        " ".join(
            str(part)
            for part in (
                raw.get("section_title"),
                raw.get("section"),
                raw.get("heading"),
                raw.get("page_start"),
                raw.get("page"),
            )
            if part
        )
    )
    text = _normalize_dedupe_text(" ".join(part for part in (item.abstract or "", item.snippet or "") if part))
    return f"{document_key}|section:{section}|text:{text[:900]}"


def _document_dedupe_key(item: EvidenceItem) -> str:
    if item.doi:
        return f"doi:{normalize_identifier(item.doi)}"
    if item.pmid:
        return f"pmid:{normalize_identifier(item.pmid)}"
    if item.pmcid:
        return f"pmcid:{normalize_identifier(item.pmcid)}"
    if item.url:
        return f"url:{str(item.url).lower().rstrip('/')}"
    if item.title:
        return f"title:{normalize_title(item.title)}"
    return repr(item)


def _normalize_dedupe_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def lexical_overlap_score(query: str, text: str) -> float:
    query_tokens = _tokens(query)
    text_tokens = _tokens(text)
    if not query_tokens or not text_tokens:
        return 0.0
    overlap = query_tokens.intersection(text_tokens)
    return min(len(overlap) / math.sqrt(len(query_tokens) * len(text_tokens)), 1.0)


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.sub(r"[^a-zA-Z0-9\s]", " ", value.lower()).split()
        if len(token) > 2
    }


def _credibility_score(item: EvidenceItem) -> float:
    source_key = getattr(item.source, "value", str(item.source))
    score = REPUTABLE_SOURCE_BONUS.get(source_key, 0.02)
    score += EVIDENCE_TYPE_BONUS.get(item.evidence_type or "", 0.0)
    score += source_trust_bonus(source_key, str(item.url), _item_text(item))
    score += evidence_type_bonus(item.evidence_type)
    url = str(item.url).lower()
    if any(domain in url for domain in REPUTABLE_DOMAINS):
        score += 0.04
    return min(score, 0.72)


def _item_text(item: EvidenceItem) -> str:
    return " ".join(
        part
        for part in (
            item.title,
            item.abstract or "",
            item.snippet or "",
            item.journal_or_publisher or "",
        )
        if part
    )


def _source_key(item: EvidenceItem) -> str:
    return getattr(item.source, "value", str(item.source))


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
