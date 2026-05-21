from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, wait
import logging
import time

from evidence_retrieval_test.src.config import EvidenceRetrievalSettings, get_settings
from evidence_retrieval_test.src.models import EvidenceItem, SearchResult
from evidence_retrieval_test.src.providers.base import BaseEvidenceProvider, ProviderError
from evidence_retrieval_test.src.providers.crawl4ai_provider import Crawl4AIProvider
from evidence_retrieval_test.src.providers.europe_pmc_provider import EuropePMCProvider
from evidence_retrieval_test.src.providers.official_health_api_provider import (
    OfficialHealthAPIProvider,
)
from evidence_retrieval_test.src.providers.pubmed_provider import PubMedProvider
from evidence_retrieval_test.src.providers.semantic_scholar_provider import (
    SemanticScholarProvider,
)
from evidence_retrieval_test.src.services.evidence_ranker import (
    deduplicate_items,
    rank_evidence_items,
)
from evidence_retrieval_test.src.services.query_builder import (
    build_evidence_query,
    build_provider_query,
    normalize_question,
)

logger = logging.getLogger(__name__)


class EvidenceSearchService:
    def __init__(
        self,
        settings: EvidenceRetrievalSettings | None = None,
        providers: Sequence[BaseEvidenceProvider] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.providers = list(providers) if providers is not None else self._default_providers()

    def search(self, question: str, top_k: int = 8) -> SearchResult:
        total_started_at = time.perf_counter()
        normalized_query = build_evidence_query(question)
        ranking_query = normalize_question(question) or question.strip()
        max_results = max(top_k, self.settings.max_results_per_provider)
        provider_errors: list[str] = []
        items: list[EvidenceItem] = []
        timings_ms: dict[str, float] = {}

        executor = ThreadPoolExecutor(max_workers=max(len(self.providers), 1))
        try:
            futures = {
                executor.submit(
                    _run_provider_search,
                    provider,
                    build_provider_query(question, provider.source_name),
                    max_results,
                ): provider
                for provider in self.providers
            }
            provider_started_at = {
                provider.source_name: time.perf_counter() for provider in self.providers
            }
            retrieval_timeout = self._effective_retrieval_timeout()
            done, pending = wait(futures, timeout=retrieval_timeout)

            for future in done:
                provider = futures[future]
                provider_key = provider.source_name
                try:
                    provider_items, elapsed_ms, error = future.result()
                    timings_ms[f"provider.{provider_key}"] = elapsed_ms
                    items.extend(provider_items)
                    if error:
                        provider_errors.append(error)
                except Exception as exc:
                    timings_ms[f"provider.{provider_key}"] = round(
                        (time.perf_counter() - provider_started_at[provider_key]) * 1000,
                        1,
                    )
                    provider_errors.append(f"{provider.source_name} unexpected error: {exc}")

            for future in pending:
                provider = futures[future]
                provider_key = provider.source_name
                timings_ms[f"provider.{provider_key}"] = round(
                    (time.perf_counter() - provider_started_at[provider_key]) * 1000,
                    1,
                )
                provider_errors.append(
                    f"{provider.source_name} exceeded retrieval budget "
                    f"({retrieval_timeout:.1f}s)"
                )
                future.cancel()
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        ranking_started_at = time.perf_counter()
        deduped = deduplicate_items(items)
        ranked = rank_evidence_items(ranking_query, deduped)
        top_items = _select_diverse_results(ranking_query, ranked, top_k)
        timings_ms["ranking"] = round((time.perf_counter() - ranking_started_at) * 1000, 1)
        timings_ms["total"] = round((time.perf_counter() - total_started_at) * 1000, 1)

        logger.info(
            "evidence search completed in %.1f ms: providers=%s results=%d errors=%d",
            timings_ms["total"],
            {key: value for key, value in timings_ms.items() if key.startswith("provider.")},
            len(top_items),
            len(provider_errors),
        )

        return SearchResult(
            query=question,
            normalized_query=normalized_query,
            total_results=len(top_items),
            items=top_items,
            provider_errors=provider_errors,
            timings_ms=timings_ms,
        )

    def _default_providers(self) -> list[BaseEvidenceProvider]:
        providers: list[BaseEvidenceProvider] = [
            PubMedProvider(self.settings),
            EuropePMCProvider(self.settings),
        ]
        if self.settings.enable_semantic_scholar:
            providers.append(SemanticScholarProvider(self.settings))
        if self.settings.enable_official_health_apis:
            providers.append(OfficialHealthAPIProvider(self.settings))
        if self.settings.enable_crawl4ai:
            providers.append(Crawl4AIProvider(self.settings))
        return providers

    def _effective_retrieval_timeout(self) -> float:
        if not any(provider.source_name == "crawl4ai" for provider in self.providers):
            return self.settings.retrieval_time_budget_seconds
        crawl_with_cleanup = self.settings.crawl_time_budget_seconds + 8.0
        return max(self.settings.retrieval_time_budget_seconds, crawl_with_cleanup)


def _run_provider_search(
    provider: BaseEvidenceProvider,
    normalized_query: str,
    max_results: int,
) -> tuple[list[EvidenceItem], float, str | None]:
    started_at = time.perf_counter()
    try:
        return (
            provider.search(normalized_query, max_results),
            round((time.perf_counter() - started_at) * 1000, 1),
            None,
        )
    except ProviderError as exc:
        return [], round((time.perf_counter() - started_at) * 1000, 1), str(exc)
    except Exception as exc:
        return (
            [],
            round((time.perf_counter() - started_at) * 1000, 1),
            f"{provider.source_name} unexpected error: {exc}",
        )


def _select_diverse_results(query: str, ranked: list[EvidenceItem], top_k: int) -> list[EvidenceItem]:
    selected: list[EvidenceItem] = []
    seen_ids: set[str] = set()

    def add(item: EvidenceItem) -> None:
        if len(selected) >= top_k or item.id in seen_ids or not _is_relevant_result(query, item):
            return
        selected.append(item)
        seen_ids.add(item.id)

    for source in (
        "official_health_api",
        "crawl4ai",
        "pubmed",
        "europe_pmc",
        "semantic_scholar",
    ):
        best = next(
            (
                item
                for item in ranked
                if _source_key(item) == source and _is_relevant_for_diversity(query, item)
            ),
            None,
        )
        if best is not None:
            add(best)

    for item in ranked:
        add(item)

    return sorted(selected, key=lambda item: item.final_score or 0.0, reverse=True)


def _source_key(item: EvidenceItem) -> str:
    return getattr(item.source, "value", str(item.source))


def _is_relevant_for_diversity(query: str, item: EvidenceItem) -> bool:
    return _is_relevant_result(query, item)


def _is_relevant_result(query: str, item: EvidenceItem) -> bool:
    score = item.final_score or 0.0
    relevance = item.relevance_score or 0.0
    if not _contains_core_query_term(_query_for_item(query, item), item):
        return False
    if _source_key(item) == "crawl4ai" and item.evidence_type in {"guideline", "clinical_resource"}:
        return score >= 0.08 and relevance >= 0.06
    return score >= 0.14 and relevance >= 0.06


def _contains_core_query_term(query: str, item: EvidenceItem) -> bool:
    core_terms = _core_query_terms(query)
    if not core_terms:
        return True
    text_tokens = _text_tokens(
        " ".join(
            part for part in (item.title, item.abstract or "", item.snippet or "") if part
        )
    )
    return _query_overlap_count(core_terms, text_tokens) >= _required_query_overlap(core_terms)


def _core_query_terms(query: str) -> set[str]:
    return _text_tokens(query)


def _text_tokens(value: str) -> set[str]:
    import re

    return {
        token
        for token in re.sub(r"[^a-zA-Z0-9\s]", " ", value.lower()).split()
        if len(token) > 1 and not token.isdigit() and token not in _NON_CONTENT_QUERY_TERMS
    }


def _term_matches_tokens(term: str, tokens: set[str]) -> bool:
    return any(_terms_match(term, token) for token in tokens)


def _query_overlap_count(query_terms: set[str], text_tokens: set[str]) -> int:
    return sum(1 for term in query_terms if _term_matches_tokens(term, text_tokens))


def _required_query_overlap(query_terms: set[str]) -> int:
    return min(2, len(query_terms))


def _terms_match(left: str, right: str) -> bool:
    if left == right:
        return True
    if len(left) >= 4 and len(right) >= 4:
        return left.startswith(right) or right.startswith(left)
    return False


def _query_for_item(query: str, item: EvidenceItem) -> str:
    if isinstance(item.raw, dict):
        query_used = item.raw.get("query_used")
        if isinstance(query_used, str) and query_used.strip():
            return f"{query} {query_used.strip()}"
    return query


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
