from __future__ import annotations

from dataclasses import dataclass
import re

@dataclass(frozen=True)
class EvidenceQueryPlan:
    original: str
    normalized: str
    content_terms: tuple[str, ...]
    intent_labels: tuple[str, ...]
    population_terms: tuple[str, ...]
    section_terms: tuple[str, ...]
    evidence_terms: tuple[str, ...]

    @property
    def ranking_query(self) -> str:
        return self.normalized

    def provider_query(self, provider_source: str) -> str:
        return self.normalized


def normalize_question(question: str) -> str:
    """
    Normalize search text without trying to classify medical meaning.
    Clinical interpretation is left to the retrievers, source ranking, and model.
    """
    text = question.strip().lower()
    text = re.sub(r"\b(\d+)\s+(kg|mg|g|mcg|ml|mmol|cm|m2)\b", r"\1\2", text)
    text = re.sub(r"[^a-z0-9\s/]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_query_plan(question: str) -> EvidenceQueryPlan:
    normalized = normalize_question(question)
    tokens = _tokens(normalized)
    return EvidenceQueryPlan(
        original=question,
        normalized=normalized,
        content_terms=tokens,
        intent_labels=("semantic",),
        population_terms=(),
        section_terms=(),
        evidence_terms=(),
    )


def build_evidence_query(question: str) -> str:
    plan = build_query_plan(question)
    return plan.ranking_query or "clinical"


def build_provider_query(question: str, provider_source: str) -> str:
    return build_query_plan(question).provider_query(provider_source)


def _tokens(value: str) -> tuple[str, ...]:
    seen: set[str] = set()
    tokens: list[str] = []
    for token in value.split():
        if token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tuple(tokens)
