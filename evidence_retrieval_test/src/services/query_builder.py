from __future__ import annotations

import re


def normalize_question(question: str) -> str:
    """
    Light normalization only: no disease lists, no stopword tables, no intent dictionaries.
    Retrieval backends interpret the clinical wording; we only clean noise.
    """
    text = question.strip()
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_evidence_query(question: str) -> str:
    """
    Query string for evidence retrieval paths. Keep this derived only from the
    user's wording; source catalogues and ranking decide what is evidence-like.
    """
    base = normalize_question(question)
    if not base:
        return "clinical"
    return base


def build_provider_query(question: str, provider_source: str) -> str:
    """
    PubMed, Europe PMC, and Semantic Scholar work best on the user's wording alone
    (metadata search), not on extra guideline boilerplate.
    """
    if provider_source in {"pubmed", "europe_pmc", "semantic_scholar"}:
        return normalize_question(question) or question.strip()
    return build_evidence_query(question)
