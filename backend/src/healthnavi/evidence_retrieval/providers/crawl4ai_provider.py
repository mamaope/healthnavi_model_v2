from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed
from dataclasses import dataclass
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from urllib.parse import quote_plus, urljoin, urlparse

import httpx

from healthnavi.evidence_retrieval.config import EvidenceRetrievalSettings
from healthnavi.evidence_retrieval.models import EvidenceItem, EvidenceSource
from healthnavi.evidence_retrieval.providers.base import BaseEvidenceProvider, ProviderError
from healthnavi.evidence_retrieval.services.evidence_policy import (
    evidence_policy_sort_key,
)
from healthnavi.evidence_retrieval.services.evidence_ranker import lexical_overlap_score
from healthnavi.evidence_retrieval.services.clinical_specificity import (
    clinical_specificity_score,
)

logger = logging.getLogger(__name__)
MAX_PDF_BYTES = 12_000_000
MAX_PDF_PAGES = 120
MAX_PDF_TEXT_CHARS = 220_000
PDF_TEXT_CACHE_VERSION = 3
MIN_PDF_TEXT_CACHE_VERSION = 2
MAX_LINKED_DOCUMENT_CANDIDATES = 3
PDF_SNIPPET_SEGMENTS = 6
GENERAL_QUERY_STOPWORDS = {
    "about",
    "after",
    "and",
    "are",
    "can",
    "does",
    "details",
    "for",
    "from",
    "how",
    "in",
    "information",
    "into",
    "is",
    "list",
    "most",
    "of",
    "options",
    "should",
    "specific",
    "the",
    "their",
    "them",
    "these",
    "this",
    "under",
    "what",
    "when",
    "where",
    "which",
    "with",
}


@dataclass(frozen=True)
class CrawlSource:
    name: str
    publisher: str
    domains: tuple[str, ...]
    topics: tuple[str, ...]
    priority: float
    seed_urls: tuple[str, ...]
    search_urls: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: dict) -> "CrawlSource":
        return cls(
            name=str(value["name"]),
            publisher=str(value.get("publisher") or value["name"]),
            domains=tuple(str(domain).lower() for domain in value.get("domains", [])),
            topics=tuple(str(topic).lower() for topic in value.get("topics", [])),
            priority=float(value.get("priority", 0.5)),
            seed_urls=tuple(str(url) for url in value.get("seed_urls", [])),
            search_urls=tuple(str(url) for url in value.get("search_urls", [])),
        )


@dataclass(frozen=True)
class CrawlTarget:
    url: str
    title_hint: str
    publisher: str
    source_name: str
    is_search_page: bool = False


@dataclass(frozen=True)
class PdfSeedCandidate:
    source_index: int
    url_index: int
    source: CrawlSource
    url: str
    title: str
    score: float
    relevance: float


class Crawl4AIProvider(BaseEvidenceProvider):
    source_name = EvidenceSource.CRAWL4AI.value

    def __init__(
        self,
        settings: EvidenceRetrievalSettings,
        sources: list[CrawlSource] | None = None,
        country_code: str | None = None,
    ) -> None:
        super().__init__(settings)
        self.sources = sources or load_crawl_sources(settings)
        self.country_code = _normalize_country_code(country_code or settings.deployment_country)

    def search(self, query: str, max_results: int) -> list[EvidenceItem]:
        if not self.settings.enable_crawl4ai:
            return []

        eligible_sources = self._eligible_sources()
        selected_sources = self._select_sources(query, eligible_sources)
        if not selected_sources:
            return []

        started_at = time.perf_counter()
        deadline = started_at + self.settings.crawl_time_budget_seconds
        focus_terms = _source_selection_terms(query, eligible_sources)
        pdf_items = self._pdf_seed_items(query, selected_sources, max_results, deadline, focus_terms)
        static_items = (
            self._static_seed_items(
                query,
                selected_sources,
                max_results,
                deadline,
                focus_terms,
            )
            if _remaining_seconds(deadline) > 0.5
            else []
        )
        browser_items: list[EvidenceItem] = []
        has_open_slots = len(_dedupe_items([*pdf_items, *static_items])) < max_results
        if self.settings.enable_crawl4ai_browser and has_open_slots:
            try:
                browser_items = asyncio.run(
                    self._crawl_for_query(
                        query,
                        selected_sources,
                        max_results,
                        deadline,
                        focus_terms,
                    )
                )
            except RuntimeError:
                loop = asyncio.new_event_loop()
                try:
                    browser_items = loop.run_until_complete(
                        self._crawl_for_query(
                            query,
                            selected_sources,
                            max_results,
                            deadline,
                            focus_terms,
                        )
                    )
                finally:
                    loop.close()
        logger.info(
            "crawl4ai search completed in %.1f ms: query=%r sources=%s static_results=%d browser_results=%d",
            (time.perf_counter() - started_at) * 1000,
            query,
            [source.name for source in selected_sources],
            len(static_items),
            len(browser_items),
        )
        combined = _dedupe_items([*pdf_items, *static_items, *browser_items])
        combined.sort(key=lambda item: item.relevance_score or 0.0, reverse=True)
        return combined[:max_results]

    def _eligible_sources(self) -> list[CrawlSource]:
        return [
            source
            for source in self.sources
            if _source_allowed_for_country(source, self.country_code)
            and any(self._is_allowed_domain(domain) for domain in source.domains)
        ]

    def _select_sources(
        self,
        query: str,
        eligible_sources: list[CrawlSource] | None = None,
    ) -> list[CrawlSource]:
        eligible_sources = eligible_sources if eligible_sources is not None else self._eligible_sources()
        selection_terms = _source_selection_terms(query, eligible_sources)
        query_terms = _core_query_terms(query)
        query_countries = _query_country_codes(query)
        preferred_country = _source_preference_country_for_query(query, self.country_code)
        selection_query = query
        scored: list[tuple[float, CrawlSource]] = []
        for source in eligible_sources:
            source_countries = _source_countries(source)
            if query_countries and source_countries and source_countries.isdisjoint(query_countries):
                continue
            source_match_terms = (
                query_terms
                if query_countries and source_countries
                else selection_terms or query_terms
            )
            topic_text = " ".join(
                (
                    *source.topics,
                    source.name,
                    source.publisher,
                )
            )
            overlap = lexical_overlap_score(selection_query, topic_text)
            match_count = _source_topic_match_count(source_match_terms, source)
            if match_count <= 0 and not _source_is_catalog_broad(source):
                continue
            if (
                len(source_match_terms) > 1
                and match_count < 2
                and not _source_is_catalog_broad(source)
            ):
                continue
            topic_signal = _source_topic_signal(source_match_terms, source)
            country_bonus = _source_country_preference_bonus(source, preferred_country)
            if query_countries and _source_matches_country_preference(source, preferred_country):
                country_bonus += 0.45
            score = (
                overlap
                + (0.18 * topic_signal)
                + (0.04 if source.search_urls else 0.0)
                + (source.priority * 0.12)
                + country_bonus
            )
            scored.append((score, source))

        scored.sort(key=lambda item: item[0], reverse=True)
        selected = [source for _, source in scored]
        selected = _ensure_global_crawl_source(selected, self.settings.crawl_max_sources)
        return selected[: self.settings.crawl_max_sources]

    async def _crawl_for_query(
        self,
        query: str,
        sources: list[CrawlSource],
        max_results: int,
        deadline: float,
        focus_terms: set[str] | None = None,
    ) -> list[EvidenceItem]:
        focus_terms = focus_terms or _source_selection_terms(query, sources)
        os.environ.setdefault(
            "CRAWL4_AI_BASE_DIRECTORY",
            str(Path(__file__).resolve().parents[2]),
        )
        os.environ.setdefault(
            "PLAYWRIGHT_BROWSERS_PATH",
            str(Path(__file__).resolve().parents[2] / ".playwright-browsers"),
        )
        try:
            from crawl4ai import AsyncWebCrawler
        except Exception as exc:
            raise ProviderError(
                "crawl4ai is enabled but could not be imported. Install it in the active Python 3.11+ environment, "
                "or set ENABLE_CRAWL4AI=false."
            ) from exc

        search_targets = self._search_targets(query, sources)
        seed_targets = self._seed_targets(query, sources)
        if not search_targets and not seed_targets:
            return []

        crawl_config = _crawl_run_config(self.settings.request_timeout_seconds)
        async with AsyncWebCrawler() as crawler:
            search_timeout = _initial_search_timeout(_remaining_seconds(deadline), bool(seed_targets))
            initial_results = await self._crawl_targets(
                crawler,
                search_targets or seed_targets,
                crawl_config,
                search_timeout,
            )
            discovered_targets = self._discover_targets(
                query,
                sources,
                [*search_targets, *seed_targets],
                initial_results,
            )
            remaining_slots = max(self.settings.crawl_max_pages - len(_content_results(initial_results)), 0)
            remaining_time = _remaining_seconds(deadline)
            followup_targets = discovered_targets[:remaining_slots]
            if not followup_targets and search_targets:
                followup_targets = seed_targets[:remaining_slots]
            if remaining_slots > 0 and followup_targets and remaining_time > 0.25:
                more_results = await self._crawl_targets(
                    crawler,
                    followup_targets,
                    crawl_config,
                    remaining_time,
                )
            else:
                more_results = []

        items = self._results_to_items(
            query,
            [*initial_results, *more_results],
            focus_terms,
        )
        items.sort(key=lambda item: item.relevance_score or 0.0, reverse=True)
        return items[:max_results]

    def _initial_targets(self, query: str, sources: list[CrawlSource]) -> list[CrawlTarget]:
        return _dedupe_targets([*self._search_targets(query, sources), *self._seed_targets(query, sources)])[
            : self.settings.crawl_max_pages
        ]

    def _search_targets(self, query: str, sources: list[CrawlSource]) -> list[CrawlTarget]:
        scored_targets: list[tuple[float, CrawlTarget]] = []
        for source in sources:
            for template in source.search_urls[: self.settings.crawl_search_pages_per_source]:
                url = template.format(query=quote_plus(query))
                if self._is_allowed_url(url):
                    scored_targets.append(
                        (
                            source.priority + 0.2,
                            CrawlTarget(
                                url=url,
                                title_hint=f"{source.name} search results",
                                publisher=source.publisher,
                                source_name=source.name,
                                is_search_page=True,
                            ),
                        )
                    )
        scored_targets.sort(key=lambda item: item[0], reverse=True)
        return _dedupe_targets([target for _, target in scored_targets])[: self.settings.crawl_max_pages]

    def _seed_targets(self, query: str, sources: list[CrawlSource]) -> list[CrawlTarget]:
        scored_targets: list[tuple[float, CrawlTarget]] = []
        for source in sources:
            for seed_score, url in self._scored_seed_urls(query, source)[:3]:
                scored_targets.append(
                    (
                        seed_score,
                        CrawlTarget(
                            url=url,
                            title_hint=_title_hint(url),
                            publisher=source.publisher,
                            source_name=source.name,
                        ),
                    )
                )

        scored_targets.sort(key=lambda item: item[0], reverse=True)
        deduped_targets = _dedupe_targets([target for _, target in scored_targets])
        return deduped_targets[: self.settings.crawl_max_pages]

    def _scored_seed_urls(self, query: str, source: CrawlSource) -> list[tuple[float, str]]:
        seed_scores = sorted(
            (
                (
                    lexical_overlap_score(
                        query,
                        f"{source.name} {source.publisher} {' '.join(source.topics)} {_title_hint(url)} {url}",
                    )
                    + _query_topic_bonus(query, url)
                    + _core_url_bonus(query, url)
                    + (source.priority * 0.18)
                    - _generic_url_penalty(url),
                    url,
                )
                for url in source.seed_urls
                if self._is_allowed_url(url) and not _is_search_like_url(url)
            ),
            reverse=True,
        )
        return seed_scores

    def _static_seed_items(
        self,
        query: str,
        sources: list[CrawlSource],
        max_results: int,
        deadline: float,
        focus_terms: set[str] | None = None,
    ) -> list[EvidenceItem]:
        focus_terms = focus_terms or _source_selection_terms(query, sources)
        scored_targets: list[tuple[float, CrawlTarget]] = []
        first_targets: list[CrawlTarget] = []
        for source in sources:
            source_seed_scores = [
                (score, url)
                for score, url in self._scored_seed_urls(query, source)[:5]
                if not _is_probable_pdf(url) and not _is_search_like_url(url)
            ]
            if source_seed_scores:
                _, first_url = source_seed_scores[0]
                first_targets.append(
                    CrawlTarget(
                        url=first_url,
                        title_hint=_title_hint(first_url),
                        publisher=source.publisher,
                        source_name=source.name,
                    )
                )
            for score, url in source_seed_scores:
                if _is_probable_pdf(url):
                    continue
                scored_targets.append(
                    (
                        score,
                        CrawlTarget(
                            url=url,
                            title_hint=_title_hint(url),
                            publisher=source.publisher,
                            source_name=source.name,
                        ),
                    )
                )
        scored_targets.sort(key=lambda item: item[0], reverse=True)
        timeout = min(float(self.settings.request_timeout_seconds), 4.0, _remaining_seconds(deadline))
        if timeout <= 0.25:
            return []

        seed_targets = _dedupe_targets(
            [*first_targets, *[target for _, target in scored_targets]]
        )[: min(self.settings.crawl_max_pages, max_results + 4)]
        items = _fetch_static_targets(
            query,
            seed_targets,
            timeout,
            self.settings,
            focus_terms,
            deadline,
        )
        if len(items) >= max_results or _remaining_seconds(deadline) <= 0.5:
            items.sort(key=lambda item: item.relevance_score or 0.0, reverse=True)
            return items[:max_results]

        open_slots = max(min(self.settings.crawl_max_pages, max_results + 6) - len(seed_targets), 0)
        if open_slots <= 0:
            items.sort(key=lambda item: item.relevance_score or 0.0, reverse=True)
            return items[:max_results]

        discovered_targets = self._discover_static_search_targets(
            query,
            sources,
            min(timeout, _remaining_seconds(deadline)),
        )
        targets = _dedupe_targets(discovered_targets)[:open_slots]
        items.extend(
            _fetch_static_targets(
                query,
                targets,
                min(timeout, _remaining_seconds(deadline)),
                self.settings,
                focus_terms,
                deadline,
            )
        )
        items.sort(key=lambda item: item.relevance_score or 0.0, reverse=True)
        return items[:max_results]

    def _discover_static_search_targets(
        self,
        query: str,
        sources: list[CrawlSource],
        timeout: float,
    ) -> list[CrawlTarget]:
        search_targets = self._search_targets(query, sources)
        if not search_targets:
            return []

        by_domain = {
            domain: source
            for source in sources
            for domain in source.domains
        }
        scored_targets: list[tuple[float, CrawlTarget]] = []
        with ThreadPoolExecutor(max_workers=min(4, max(len(search_targets), 1))) as executor:
            futures = {
                executor.submit(
                    _fetch_static_search_links,
                    query,
                    target,
                    by_domain,
                    timeout,
                ): target
                for target in search_targets
            }
            for future in as_completed(futures):
                scored_targets.extend(future.result())

        scored_targets.sort(key=lambda item: item[0], reverse=True)
        return _dedupe_targets(
            [target for _, target in scored_targets]
        )[: self.settings.crawl_max_pages]

    def _pdf_seed_items(
        self,
        query: str,
        sources: list[CrawlSource],
        max_results: int,
        deadline: float,
        focus_terms: set[str] | None = None,
    ) -> list[EvidenceItem]:
        focus_terms = focus_terms or _source_selection_terms(query, sources)
        candidates: list[PdfSeedCandidate] = []
        for source_index, source in enumerate(sources):
            scored_urls = [
                (
                    lexical_overlap_score(
                        query,
                        f"{source.name} {source.publisher} {' '.join(source.topics)} {_title_hint(url)} {url}",
                    )
                    + _query_topic_bonus(query, url)
                    + _core_url_bonus(query, url)
                    + (source.priority * 0.18),
                    url_index,
                    url,
                )
                for url_index, url in enumerate(source.seed_urls)
            ]
            for score, url_index, url in sorted(scored_urls, reverse=True):
                if not _is_probable_pdf(url) or not self._is_allowed_url(url):
                    continue
                title = _title_hint(url)
                evidence_text = f"{source.name} {source.publisher} {' '.join(source.topics)} {title} {url}"
                relevance = max(lexical_overlap_score(query, evidence_text), score)
                if relevance < 0.08 or not _content_matches_core_query(query, title, url, evidence_text, focus_terms):
                    continue
                candidates.append(
                    PdfSeedCandidate(
                        source_index=source_index,
                        url_index=url_index,
                        source=source,
                        url=url,
                        title=title,
                        score=score,
                        relevance=relevance,
                    )
                )

        if not candidates:
            return []

        items: list[EvidenceItem] = []
        completion_timeout = max(_remaining_seconds(deadline) - 0.25, 0.0)
        if completion_timeout <= 0:
            return [
                _pdf_seed_metadata_item(candidate)
                for candidate in candidates[:max_results]
            ]

        max_workers = min(4, max(len(candidates), 1))
        executor = ThreadPoolExecutor(max_workers=max_workers)
        try:
            futures = {
                executor.submit(
                    _fetch_pdf_seed_item,
                    query=query,
                    source=candidate.source,
                    url=candidate.url,
                    source_score=candidate.score,
                    deadline=deadline,
                    settings=self.settings,
                    focus_terms=focus_terms,
                ): candidate
                for candidate in candidates
            }
            completed_candidates: set[PdfSeedCandidate] = set()
            try:
                completed = as_completed(futures, timeout=completion_timeout)
                for future in completed:
                    candidate = futures[future]
                    completed_candidates.add(candidate)
                    pdf_items = future.result()
                    if not pdf_items:
                        items.append(_pdf_seed_metadata_item(candidate))
                        continue
                    items.extend(pdf_items)
            except FuturesTimeoutError:
                logger.info(
                    "pdf seed crawl returned %d partial items after deadline with %d pending PDFs",
                    len(items),
                    sum(1 for future in futures if not future.done()),
                )
            for future, candidate in futures.items():
                if candidate in completed_candidates:
                    continue
                if future.done():
                    try:
                        pdf_items = future.result()
                    except Exception as exc:
                        logger.debug("pdf seed crawl failed for %s: %s", candidate.url, exc)
                        pdf_items = []
                    if pdf_items:
                        items.extend(pdf_items)
                    else:
                        items.append(_pdf_seed_metadata_item(candidate))
                    continue
                future.cancel()
                if len(items) < max_results:
                    items.append(_pdf_seed_metadata_item(candidate))
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        if not items:
            items = [
                _pdf_seed_metadata_item(candidate)
                for candidate in candidates[:max_results]
            ]
        items.sort(key=lambda item: item.relevance_score or 0.0, reverse=True)
        return _dedupe_items(items)[:max_results]

    async def _crawl_targets(
        self,
        crawler,
        targets: list[CrawlTarget],
        crawl_config,
        timeout_seconds: float,
    ) -> list[tuple[CrawlTarget, object]]:
        if not targets:
            return []
        if timeout_seconds <= 0:
            logger.info("crawl4ai skipped %d targets because the time budget was exhausted", len(targets))
            return []

        async def crawl_one(target: CrawlTarget) -> tuple[CrawlTarget, object | None]:
            try:
                if crawl_config is None:
                    result = await crawler.arun(url=target.url)
                else:
                    result = await crawler.arun(url=target.url, config=crawl_config)
                return target, result
            except Exception as exc:
                logger.warning("crawl4ai failed for %s: %s", target.url, exc)
                return target, None

        tasks = [asyncio.create_task(crawl_one(target)) for target in targets]
        done, pending = await asyncio.wait(tasks, timeout=timeout_seconds)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        if pending:
            logger.info(
                "crawl4ai cancelled %d unfinished targets after %.1f seconds",
                len(pending),
                timeout_seconds,
            )
        crawled = [task.result() for task in done if not task.cancelled() and task.exception() is None]
        return [(target, result) for target, result in crawled if result is not None]

    def _discover_targets(
        self,
        query: str,
        sources: list[CrawlSource],
        existing_targets: list[CrawlTarget],
        crawl_results: list[tuple[CrawlTarget, object]],
    ) -> list[CrawlTarget]:
        by_domain = {
            domain: source
            for source in sources
            for domain in source.domains
        }
        seen_urls = {target.url for target in existing_targets}
        scored_targets: list[tuple[float, CrawlTarget]] = []

        for target, result in crawl_results:
            if not target.is_search_page:
                continue
            for link_url, link_text in _extract_links(result, target.url):
                if link_url in seen_urls or not self._is_allowed_url(link_url):
                    continue
                source = _source_for_url(link_url, by_domain)
                if source is None:
                    continue
                link_score = lexical_overlap_score(query, f"{link_text} {link_url} {source.name} {source.publisher}")
                if link_score < 0.04:
                    continue
                seen_urls.add(link_url)
                scored_targets.append(
                    (
                        link_score,
                        CrawlTarget(
                            url=link_url,
                            title_hint=link_text or _title_hint(link_url),
                            publisher=source.publisher,
                            source_name=source.name,
                        ),
                    )
                )

        scored_targets.sort(key=lambda item: item[0], reverse=True)
        return [target for _, target in scored_targets]

    def _results_to_items(
        self,
        query: str,
        crawl_results: list[tuple[CrawlTarget, object]],
        focus_terms: set[str],
    ) -> list[EvidenceItem]:
        items: list[EvidenceItem] = []
        for target, result in crawl_results:
            if target.is_search_page:
                continue
            if getattr(result, "success", True) is False:
                continue
            markdown = _markdown_text(result).strip()
            if len(markdown) < 120:
                continue
            snippet = _best_snippet(query, markdown)
            if not _content_matches_core_query(query, target.title_hint, target.url, snippet, focus_terms):
                continue
            relevance = lexical_overlap_score(query, f"{target.title_hint} {snippet}")
            if relevance < 0.03:
                continue
            items.append(
                EvidenceItem(
                    id=f"crawl4ai:{_canonical_url(target.url)}",
                    source=EvidenceSource.CRAWL4AI,
                    title=_result_title(result) or target.title_hint,
                    abstract=None,
                    snippet=snippet,
                    authors=[],
                    journal_or_publisher=target.publisher,
                    url=target.url,
                    full_text_url=target.url,
                    open_access=True,
                    evidence_type=_evidence_type(target.url, target.title_hint, markdown),
                    relevance_score=round(relevance, 4),
                    raw={
                        "source_name": target.source_name,
                        "markdown_preview": markdown[:4000],
                    },
                )
            )
        return items

    def _is_allowed_url(self, url: str) -> bool:
        host = urlparse(url).netloc.lower().replace("www.", "")
        return self._is_allowed_domain(host)

    def _is_allowed_domain(self, host: str) -> bool:
        clean_host = host.lower().replace("www.", "")
        return any(
            clean_host == domain or clean_host.endswith(f".{domain}")
            for domain in self.settings.crawl_allowed_domains
        )


def load_crawl_sources(settings: EvidenceRetrievalSettings) -> list[CrawlSource]:
    catalog_path = (
        Path(settings.crawl_source_catalog_path)
        if settings.crawl_source_catalog_path
        else Path(__file__).with_name("crawl_sources.json")
    )
    try:
        raw_sources = json.loads(catalog_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ProviderError(f"Crawl source catalog cannot be read: {catalog_path}") from exc
    except json.JSONDecodeError as exc:
        raise ProviderError(f"Crawl source catalog is invalid JSON: {catalog_path}") from exc
    return [CrawlSource.from_dict(source) for source in raw_sources]


def _crawl_run_config(timeout_seconds: int):
    try:
        from crawl4ai import CacheMode, CrawlerRunConfig
    except ImportError:
        return None

    timeout_ms = max(timeout_seconds, 1) * 1000
    try:
        return CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            check_robots_txt=True,
            page_timeout=timeout_ms,
            wait_until="domcontentloaded",
            word_count_threshold=20,
        )
    except TypeError:
        return CrawlerRunConfig(cache_mode=CacheMode.ENABLED)


def _source_allowed_for_country(source: CrawlSource, country_code: str | None) -> bool:
    if country_code is None:
        return True
    source_countries = _source_countries(source)
    return not source_countries or country_code in source_countries


def _source_country_preference_bonus(
    source: CrawlSource,
    preferred_country: str | None,
) -> float:
    if not preferred_country:
        return 0.0
    if _source_matches_country_preference(source, preferred_country):
        return 0.54
    if not _source_countries(source):
        return 0.03
    return 0.0


def _source_matches_country_preference(
    source: CrawlSource,
    preferred_country: str | None,
) -> bool:
    return bool(preferred_country and preferred_country in _source_countries(source))


def _source_preference_country_for_query(
    query: str,
    configured_country_code: str | None,
) -> str | None:
    query_countries = _query_country_codes(query)
    if len(query_countries) == 1:
        return next(iter(query_countries))
    if len(query_countries) > 1:
        return None
    return _normalize_country_code(configured_country_code)


def _query_country_codes(query: str) -> set[str]:
    text = query.lower()
    return {
        code
        for code, markers in _COUNTRY_MARKERS.items()
        if any(marker in text for marker in markers)
    }


def _source_countries(source: CrawlSource) -> set[str]:
    haystack = " ".join(
        (
            source.name,
            source.publisher,
            " ".join(source.domains),
            " ".join(source.topics),
            " ".join(source.seed_urls),
            " ".join(source.search_urls),
        )
    ).lower()
    return {
        code
        for code, markers in _COUNTRY_MARKERS.items()
        if any(marker in haystack for marker in markers)
    }


def _normalize_country_code(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    if normalized in {"UGANDA", "UG", "UGA"}:
        return "UG"
    if normalized in {"KENYA", "KE", "KEN"}:
        return "KE"
    if normalized in {"TANZANIA", "TZ", "TZA"}:
        return "TZ"
    if normalized == "":
        return None
    return normalized


_COUNTRY_MARKERS = {
    "UG": (
        "uganda",
        "ugandan",
        "health.go.ug",
        "library.health.go.ug",
        "nda.or.ug",
        "uniph.go.ug",
        "cphl.go.ug",
        "qadash.cphl.go.ug",
        "uci.or.ug",
        "ulii.org",
        "idi.mak.ac.ug",
        "elearning.idi.co.ug",
        "uga-",
    ),
    "KE": ("kenya", "kenyan", "health.go.ke"),
    "TZ": ("tanzania", "tanzanian", "moh.go.tz", "nmcp.go.tz"),
}


def _ensure_global_crawl_source(
    selected_sources: list[CrawlSource],
    max_sources: int,
) -> list[CrawlSource]:
    if max_sources <= 1:
        return selected_sources
    selected_window = selected_sources[:max_sources]
    if any(_is_global_crawl_source(source) for source in selected_window):
        return selected_sources

    global_source = next(
        (
            source
            for source in selected_sources[max_sources:]
            if _is_global_crawl_source(source)
        ),
        None,
    )
    if global_source is None:
        return selected_sources

    return [
        *selected_sources[: max_sources - 1],
        global_source,
        *[
            source
            for source in selected_sources[max_sources - 1 :]
            if source != global_source
        ],
    ]


def _is_global_crawl_source(source: CrawlSource) -> bool:
    return not _source_countries(source)


def _source_for_url(url: str, by_domain: dict[str, CrawlSource]) -> CrawlSource | None:
    host = urlparse(url).netloc.lower().replace("www.", "")
    for domain, source in by_domain.items():
        if host == domain or host.endswith(f".{domain}"):
            return source
    return None


def _fetch_static_search_links(
    query: str,
    target: CrawlTarget,
    by_domain: dict[str, CrawlSource],
    timeout: float,
) -> list[tuple[float, CrawlTarget]]:
    headers = {"User-Agent": "EmpiricoEvidenceRetrieval/0.1"}
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
            response = client.get(target.url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.debug("static search fetch failed for %s: %s", target.url, exc)
        return []

    content_type = response.headers.get("content-type", "").lower()
    if "text/html" not in content_type and "application/xhtml" not in content_type:
        return []

    scored_targets: list[tuple[float, CrawlTarget]] = []
    for link_url, link_text in _extract_html_links(response.text, str(response.url)):
        if _is_search_like_url(link_url):
            continue
        source = _source_for_url(link_url, by_domain)
        if source is None:
            continue
        score = lexical_overlap_score(
            query,
            f"{link_text} {link_url} {source.name} {source.publisher} {' '.join(source.topics)}",
        )
        score += _query_topic_bonus(query, link_url)
        score += source.priority * 0.08
        if score < 0.08:
            continue
        scored_targets.append(
            (
                score,
                CrawlTarget(
                    url=link_url,
                    title_hint=link_text or _title_hint(link_url),
                    publisher=source.publisher,
                    source_name=source.name,
                ),
            )
        )
    return scored_targets


def _fetch_static_targets(
    query: str,
    targets: list[CrawlTarget],
    timeout: float,
    settings: EvidenceRetrievalSettings,
    focus_terms: set[str],
    deadline: float | None = None,
) -> list[EvidenceItem]:
    if not targets or timeout <= 0.25:
        return []
    items: list[EvidenceItem] = []
    max_workers = min(6, max(len(targets), 1))
    completion_timeout = None
    if deadline is not None:
        completion_timeout = max(_remaining_seconds(deadline) - 0.25, 0.0)
        if completion_timeout <= 0:
            return []

    executor = ThreadPoolExecutor(max_workers=max_workers)
    try:
        futures = {
            executor.submit(_fetch_static_target, query, target, timeout, settings, focus_terms): target
            for target in targets
        }
        try:
            completed = as_completed(futures, timeout=completion_timeout)
            for future in completed:
                item = future.result()
                if item is not None:
                    items.append(item)
        except FuturesTimeoutError:
            logger.info(
                "static crawl returned %d partial items after deadline with %d pending targets",
                len(items),
                sum(1 for future in futures if not future.done()),
            )
        for future in futures:
            if not future.done():
                future.cancel()
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
    return items


def _fetch_static_target(
    query: str,
    target: CrawlTarget,
    timeout: float,
    settings: EvidenceRetrievalSettings,
    focus_terms: set[str],
) -> EvidenceItem | None:
    headers = {"User-Agent": "EmpiricoEvidenceRetrieval/0.1"}
    cached = _read_static_cache(settings, target.url)
    retrieval_mode = "static_html_cache" if cached is not None else ""
    if cached is None:
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
                response = client.get(target.url)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.debug("static guideline fetch failed for %s: %s", target.url, exc)
            cached = _read_static_cache(settings, target.url, allow_stale=True)
            if cached is None:
                return None
            retrieval_mode = "static_html_stale_cache"
        else:
            final_url = str(response.url)
            content_type = response.headers.get("content-type", "").lower()
            html = response.text
            _write_static_cache(settings, target.url, final_url, content_type, html)
            retrieval_mode = "static_html"
    if cached is not None:
        final_url = str(cached.get("final_url") or target.url)
        content_type = str(cached.get("content_type") or "").lower()
        html = str(cached.get("html") or "")

    if "text/html" not in content_type and "application/xhtml" not in content_type:
        return None
    markdown = _html_to_text(html)
    if len(markdown) < 120:
        return None
    page_title = _html_title(html) or target.title_hint

    trusted_guideline_url = _is_trusted_guideline_url(final_url)
    snippet = _best_snippet(
        query,
        markdown,
        max_chars=2200 if trusted_guideline_url else 1200,
        max_segments=4 if trusted_guideline_url else 2,
    )
    html_item: EvidenceItem | None = None
    if _content_matches_core_query(query, page_title, final_url, snippet, focus_terms):
        relevance = lexical_overlap_score(query, f"{page_title} {snippet}")
        evidence_type = _evidence_type(final_url, page_title, markdown)
        policy_tier, type_tier = evidence_policy_sort_key(
            source=EvidenceSource.CRAWL4AI.value,
            evidence_type=evidence_type,
            url=final_url,
            text=f"{page_title} {target.publisher} {snippet}",
        )
        min_relevance = 0.04 if trusted_guideline_url else 0.08
        if relevance >= min_relevance:
            html_item = EvidenceItem(
                id=f"crawl4ai:{_canonical_url(final_url)}",
                source=EvidenceSource.CRAWL4AI,
                title=page_title,
                abstract=None,
                snippet=snippet,
                authors=[],
                journal_or_publisher=target.publisher,
                url=final_url,
                full_text_url=final_url,
                open_access=True,
                evidence_type=evidence_type,
                relevance_score=round(relevance, 4),
                raw={
                    "source_name": target.source_name,
                    "retrieval_mode": retrieval_mode,
                    "source_trust_tier": policy_tier,
                    "evidence_type_tier": type_tier,
                    "markdown_preview": markdown[:4000],
                },
            )

    linked_document_item = _fetch_linked_document_item(
        query=query,
        html=html,
        base_url=final_url,
        page_title=page_title,
        target=target,
        timeout=timeout,
        settings=settings,
        focus_terms=focus_terms,
    )
    return _best_static_item_for_query(query, html_item, linked_document_item)


def _fetch_linked_document_item(
    *,
    query: str,
    html: str,
    base_url: str,
    page_title: str,
    target: CrawlTarget,
    timeout: float,
    settings: EvidenceRetrievalSettings,
    focus_terms: set[str],
) -> EvidenceItem | None:
    candidates = _candidate_document_links_from_html(
        query=query,
        html=html,
        base_url=base_url,
        page_title=page_title,
        settings=settings,
    )
    for link_score, document_url, link_text in candidates[:MAX_LINKED_DOCUMENT_CANDIDATES]:
        fetched = _fetch_pdf_text(document_url, timeout, settings)
        if fetched is None:
            continue

        unpacked = _unpack_pdf_text_result(fetched)
        if unpacked is None:
            continue
        final_url, pdf_text, pages_extracted, page_texts = unpacked
        title = _document_title_from_context(page_title, link_text, final_url)
        snippet, snippet_page = _best_pdf_snippet_with_page(
            query,
            pdf_text,
            page_texts,
            max_chars=2400,
            max_segments=PDF_SNIPPET_SEGMENTS,
        )
        if not snippet or not _content_matches_core_query(query, title, final_url, snippet, focus_terms):
            continue

        relevance = max(
            lexical_overlap_score(query, f"{title} {target.publisher} {snippet}"),
            link_score,
        )
        if relevance < 0.06:
            continue

        evidence_type = _evidence_type(final_url, title, snippet)
        policy_tier, type_tier = evidence_policy_sort_key(
            source=EvidenceSource.CRAWL4AI.value,
            evidence_type=evidence_type,
            url=final_url,
            text=f"{title} {target.publisher} {snippet}",
        )
        raw = {
            "source_name": target.source_name,
            "retrieval_mode": "linked_pdf_text",
            "generic_link_text": _is_generic_document_link_text(link_text),
            "source_page_url": base_url,
            "source_trust_tier": policy_tier,
            "evidence_type_tier": type_tier,
            "pdf_pages_extracted": pages_extracted,
        }
        if snippet_page is not None and snippet_page > 0:
            raw["page_start"] = snippet_page
            raw["page_label"] = f"p. {snippet_page}"
        return EvidenceItem(
            id=f"crawl4ai:{_canonical_url(final_url)}",
            source=EvidenceSource.CRAWL4AI,
            title=title,
            abstract=None,
            snippet=snippet,
            authors=[],
            journal_or_publisher=target.publisher,
            url=final_url,
            full_text_url=final_url,
            open_access=True,
            evidence_type=evidence_type,
            relevance_score=round(relevance, 4),
            raw=raw,
        )
    return None


def _best_static_item_for_query(
    query: str,
    html_item: EvidenceItem | None,
    linked_document_item: EvidenceItem | None,
) -> EvidenceItem | None:
    if html_item is None:
        return linked_document_item
    if linked_document_item is None:
        return html_item
    html_score = _static_item_query_quality(query, html_item)
    linked_score = _static_item_query_quality(query, linked_document_item)
    return html_item if html_score >= linked_score else linked_document_item


def _static_item_query_quality(query: str, item: EvidenceItem) -> float:
    snippet = item.snippet or item.abstract or ""
    text = f"{item.title} {snippet}"
    core_terms = _core_query_terms(query)
    score = lexical_overlap_score(query, text)
    score += 0.12 * _query_overlap_count(core_terms, _text_tokens(text))
    if item.evidence_type == "guideline":
        score += 0.18
    if _paragraph_contains_inline_list(snippet):
        score += 0.35
    if _paragraph_looks_like_low_value_pdf_context(snippet.lower()):
        score -= 0.45
    raw = item.raw if isinstance(item.raw, dict) else {}
    if raw.get("retrieval_mode") == "linked_pdf_text":
        score += 0.12
    if raw.get("retrieval_mode") == "linked_pdf_text" and raw.get("generic_link_text"):
        score -= 0.05 if _title_or_url_matches_query(query, item.title, str(item.url)) else 0.35
    if not _is_probable_pdf(str(item.url)):
        score += 0.08
    return score


def _candidate_document_links_from_html(
    *,
    query: str,
    html: str,
    base_url: str,
    page_title: str,
    settings: EvidenceRetrievalSettings,
) -> list[tuple[float, str, str]]:
    candidates: list[tuple[float, str, str]] = []
    seen_urls: set[str] = set()
    base_host = _normalized_host(base_url)
    for link_url, link_text in _extract_html_links(html, base_url):
        canonical_url = _canonical_url(link_url)
        if canonical_url in seen_urls:
            continue
        if not _url_allowed_by_settings(link_url, settings):
            continue
        if not _looks_like_document_download_link(link_url, link_text):
            continue
        if _is_generic_document_link_text(link_text) and not _title_or_url_matches_query(
            query,
            page_title,
            base_url,
        ):
            continue
        seen_urls.add(canonical_url)
        score = lexical_overlap_score(query, f"{page_title} {link_text} {link_url}")
        score += _query_topic_bonus(query, link_url)
        link_host = _normalized_host(link_url)
        if _same_site(base_host, link_host):
            score += 0.28
        elif link_host:
            score -= 0.12
        if _is_probable_pdf(link_url):
            score += 0.18
        if _looks_like_primary_download_link(link_url, link_text):
            score += 0.16
        candidates.append((score, link_url, link_text))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates


def _looks_like_document_download_link(url: str, link_text: str) -> bool:
    if _is_search_like_url(url):
        return False
    text = f"{link_text} {urlparse(url).path}".lower()
    if _is_probable_pdf(url):
        return True
    if re.search(r"\.(?:doc|docx|pdf)$", urlparse(url).path.lower()):
        return True
    if "/bitstream/" in text or "/bitstreams/" in text:
        return True
    return bool(
        re.search(
            r"\b(download|full\s*text|pdf|publication|guideline|document|annex)\b",
            text,
        )
    )


def _looks_like_primary_download_link(url: str, link_text: str) -> bool:
    text = f"{link_text} {urlparse(url).path}".lower()
    return "download" in text or "/bitstream/" in text or "/bitstreams/" in text


def _is_generic_document_link_text(link_text: str) -> bool:
    cleaned = _clean_html_text(link_text).lower()
    if not cleaned:
        return True
    cleaned = re.sub(r"\([^)]*\)", " ", cleaned)
    cleaned = re.sub(r"[^a-z0-9\s-]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return bool(
        re.fullmatch(
            r"(download|full text|pdf|document|publication|guideline|annex|view|open"
            r"|pdf version of this title)"
            r"(?:\s+(download|full text|pdf|document|publication|guideline|annex|view|open))*",
            cleaned,
        )
    )


def _title_or_url_matches_query(query: str, title: str, url: str) -> bool:
    query_terms = _core_query_terms(query)
    if not query_terms:
        return True
    title_url_tokens = _text_tokens(f"{title} {url}")
    return _query_overlap_count(query_terms, title_url_tokens) >= 1


def _normalized_host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _same_site(left_host: str, right_host: str) -> bool:
    if not left_host or not right_host:
        return False
    if left_host == right_host:
        return True
    left_parts = left_host.split(".")
    right_parts = right_host.split(".")
    if len(left_parts) < 2 or len(right_parts) < 2:
        return False
    return ".".join(left_parts[-2:]) == ".".join(right_parts[-2:])


def _url_allowed_by_settings(url: str, settings: EvidenceRetrievalSettings) -> bool:
    host = urlparse(url).netloc.lower().replace("www.", "")
    return any(
        host == domain or host.endswith(f".{domain}")
        for domain in settings.crawl_allowed_domains
    )


def _document_title_from_context(page_title: str, link_text: str, url: str) -> str:
    cleaned_link_text = _clean_html_text(link_text)
    if cleaned_link_text and not re.fullmatch(
        r"(download|full\s*text|pdf|document|publication|pdf\s+version\s+of\s+this\s+title)"
        r"(?:\s*\([^)]*\))?",
        cleaned_link_text,
        flags=re.IGNORECASE,
    ):
        return cleaned_link_text
    return page_title or _title_hint(url)


def _fetch_pdf_seed_item(
    *,
    query: str,
    source: CrawlSource,
    url: str,
    source_score: float,
    deadline: float,
    settings: EvidenceRetrievalSettings,
    focus_terms: set[str],
) -> list[EvidenceItem]:
    remaining = _remaining_seconds(deadline)
    if remaining <= 1.0:
        return []

    timeout = min(float(settings.request_timeout_seconds), 6.0, remaining)
    fetched = _fetch_pdf_text(url, timeout, settings)
    if fetched is None:
        return []

    unpacked = _unpack_pdf_text_result(fetched)
    if unpacked is None:
        return []
    final_url, pdf_text, pages_extracted, page_texts = unpacked
    title = source.name or _title_hint(final_url)
    passages = _best_pdf_passages_with_pages(
        query,
        pdf_text,
        page_texts,
        max_chars=2400,
        max_segments=PDF_SNIPPET_SEGMENTS,
    )
    items: list[EvidenceItem] = []
    for passage_index, (snippet, snippet_page, passage_score) in enumerate(passages, start=1):
        if not snippet or not _content_matches_core_query(query, title, final_url, snippet, focus_terms):
            continue

        reserved_passage_bonus = (
            0.75
            if passage_index <= 2 and snippet_page is not None and snippet_page > 0
            else 0.0
        )
        relevance = max(
            lexical_overlap_score(query, f"{title} {source.publisher} {snippet}"),
            source_score,
            passage_score + reserved_passage_bonus,
        )
        if relevance < 0.06:
            continue

        evidence_type = _evidence_type(final_url, title, snippet)
        policy_tier, type_tier = evidence_policy_sort_key(
            source=EvidenceSource.CRAWL4AI.value,
            evidence_type=evidence_type,
            url=final_url,
            text=f"{title} {source.publisher} {snippet}",
        )
        raw = {
            "source_name": source.name,
            "retrieval_mode": "pdf_text",
            "source_trust_tier": policy_tier,
            "evidence_type_tier": type_tier,
            "pdf_pages_extracted": pages_extracted,
            "passage_rank": passage_index,
            "passage_id": f"{_canonical_url(final_url)}:{snippet_page or passage_index}:{passage_index}",
        }
        if snippet_page is not None and snippet_page > 0:
            raw["page_start"] = snippet_page
            raw["page_label"] = f"p. {snippet_page}"
        items.append(
            EvidenceItem(
                id=f"crawl4ai:{_canonical_url(final_url)}#passage={snippet_page or passage_index}-{passage_index}",
                source=EvidenceSource.CRAWL4AI,
                title=title,
                abstract=None,
                snippet=snippet,
                authors=[],
                journal_or_publisher=source.publisher,
                url=final_url,
                full_text_url=final_url,
                open_access=True,
                evidence_type=evidence_type,
                relevance_score=round(relevance, 4),
                raw=raw,
            )
        )
    return items


def _pdf_seed_metadata_item(candidate: PdfSeedCandidate) -> EvidenceItem:
    source = candidate.source
    return EvidenceItem(
        id=f"crawl4ai:{_canonical_url(candidate.url)}",
        source=EvidenceSource.CRAWL4AI,
        title=candidate.title,
        snippet=(
            f"{source.name} from {source.publisher}. "
            f"Approved guideline catalogue PDF. Topics: {', '.join(source.topics[:12])}."
        ),
        authors=[],
        journal_or_publisher=source.publisher,
        url=candidate.url,
        full_text_url=candidate.url,
        open_access=True,
        evidence_type="guideline",
        relevance_score=round(candidate.relevance, 4),
        raw={
            "source_name": source.name,
            "retrieval_mode": "pdf_seed_metadata",
        },
    )


def _fetch_pdf_text(
    url: str,
    timeout: float,
    settings: EvidenceRetrievalSettings,
) -> tuple[str, str, int, list[tuple[int, str]]] | None:
    cached = _read_pdf_text_cache(settings, url)
    if cached is not None:
        return cached

    headers = {"User-Agent": "EmpiricoEvidenceRetrieval/0.1"}
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
            response = client.get(url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.debug("pdf guideline fetch failed for %s: %s", url, exc)
        return _read_pdf_text_cache(settings, url, allow_stale=True)

    content = response.content
    content_type = response.headers.get("content-type", "").lower()
    looks_like_pdf_bytes = content.lstrip().startswith(b"%PDF") if content else False
    if (
        "pdf" not in content_type
        and not _is_probable_pdf(str(response.url))
        and not looks_like_pdf_bytes
    ):
        return None
    if not content or len(content) > MAX_PDF_BYTES:
        logger.debug("pdf guideline skipped for %s: size=%d", url, len(content))
        return None

    extracted = _extract_pdf_text(content)
    if extracted is None:
        return None
    text, pages_extracted, page_texts = extracted
    final_url = str(response.url)
    _write_pdf_text_cache(settings, url, final_url, text, pages_extracted, page_texts)
    return final_url, text, pages_extracted, page_texts


def _extract_pdf_text(content: bytes) -> tuple[str, int, list[tuple[int, str]]] | None:
    try:
        from PyPDF2 import PdfReader
    except Exception:
        logger.debug("PyPDF2 is not installed; PDF text extraction is disabled")
        return None

    try:
        reader = PdfReader(BytesIO(content))
    except Exception as exc:
        logger.debug("could not open PDF for text extraction: %s", exc)
        return None

    text_parts: list[str] = []
    pages_extracted = 0
    page_texts: list[tuple[int, str]] = []
    for page_number, page in enumerate(reader.pages[:MAX_PDF_PAGES], start=1):
        try:
            page_text = page.extract_text() or ""
        except Exception:
            continue
        cleaned = _clean_html_text(page_text)
        if not cleaned:
            continue
        text_parts.append(cleaned)
        page_texts.append((page_number, cleaned))
        pages_extracted += 1
        if sum(len(part) for part in text_parts) >= MAX_PDF_TEXT_CHARS:
            break

    text = "\n\n".join(text_parts)[:MAX_PDF_TEXT_CHARS]
    if len(text) < 120:
        return None
    return text, pages_extracted, page_texts


def _unpack_pdf_text_result(
    fetched: object,
) -> tuple[str, str, int, list[tuple[int, str]]] | None:
    if not isinstance(fetched, tuple) or len(fetched) < 3:
        return None
    final_url = str(fetched[0])
    pdf_text = str(fetched[1])
    try:
        pages_extracted = int(fetched[2])
    except (TypeError, ValueError):
        pages_extracted = 0
    page_texts: list[tuple[int, str]] = []
    if len(fetched) >= 4 and isinstance(fetched[3], list):
        for entry in fetched[3]:
            page_number: int | None = None
            page_text = ""
            if isinstance(entry, dict):
                try:
                    page_number = int(entry.get("page_number") or entry.get("page") or 0)
                except (TypeError, ValueError):
                    page_number = None
                page_text = str(entry.get("text") or "")
            elif isinstance(entry, tuple) and len(entry) >= 2:
                try:
                    page_number = int(entry[0])
                except (TypeError, ValueError):
                    page_number = None
                page_text = str(entry[1] or "")
            if page_number and page_text.strip():
                page_texts.append((page_number, page_text))
    if not page_texts and pdf_text.strip():
        page_texts = _synthetic_pdf_text_chunks(pdf_text)
    return final_url, pdf_text, pages_extracted, page_texts


def _synthetic_pdf_text_chunks(
    pdf_text: str,
    *,
    chunk_chars: int = 4200,
    overlap_chars: int = 500,
) -> list[tuple[int, str]]:
    compact = pdf_text.strip()
    if not compact:
        return []
    chunks: list[tuple[int, str]] = []
    start = 0
    chunk_index = 1
    while start < len(compact):
        end = min(start + chunk_chars, len(compact))
        if end < len(compact):
            boundary = compact.rfind("\n\n", start + chunk_chars // 2, end)
            if boundary > start:
                end = boundary
        chunk = compact[start:end].strip()
        if chunk:
            chunks.append((-chunk_index, chunk))
            chunk_index += 1
        if end >= len(compact):
            break
        start = max(end - overlap_chars, start + 1)
    return chunks


def _best_pdf_snippet_with_page(
    query: str,
    pdf_text: str,
    page_texts: list[tuple[int, str]],
    max_chars: int = 1200,
    max_segments: int = 2,
) -> tuple[str, int | None]:
    if not page_texts:
        return _best_snippet(query, pdf_text, max_chars=max_chars, max_segments=max_segments), None

    core_terms = _core_query_terms(query)
    candidates: list[tuple[float, int, str, float]] = []
    for page_number, page_text in page_texts:
        snippet = _best_snippet(
            query,
            page_text,
            max_chars=min(max_chars, 1400),
            max_segments=1,
        )
        if not snippet:
            continue
        score = _snippet_score(query, snippet, core_terms)
        score += lexical_overlap_score(query, snippet)
        candidates.append((score, page_number, snippet))

    if not candidates:
        return _best_snippet(query, pdf_text, max_chars=max_chars, max_segments=max_segments), None

    candidates.sort(key=lambda item: item[0], reverse=True)
    selected = candidates[:max_segments]
    best_page = selected[0][1]
    ordered_snippets = [snippet for _score, _page, snippet in sorted(selected, key=lambda item: item[1])]
    return _compact_text(" ... ".join(ordered_snippets), max_chars), best_page


def _best_pdf_passages_with_pages(
    query: str,
    pdf_text: str,
    page_texts: list[tuple[int, str]],
    max_chars: int = 1200,
    max_segments: int = 3,
) -> list[tuple[str, int | None, float]]:
    if not page_texts:
        snippet = _best_snippet(query, pdf_text, max_chars=max_chars, max_segments=max_segments)
        if not snippet:
            return []
        return [(snippet, None, _snippet_score(query, snippet, _core_query_terms(query)))]

    core_terms = _core_query_terms(query)
    candidates: list[tuple[float, int, str]] = []
    for page_number, page_text in page_texts:
        snippet = _best_snippet(
            query,
            page_text,
            max_chars=min(max_chars, 1400),
            max_segments=1,
        )
        snippet = _pdf_section_opening_snippet_if_helpful(
            query=query,
            page_text=page_text,
            snippet=snippet,
            max_chars=max_chars,
        )
        if not snippet:
            continue
        score = _snippet_score(query, snippet, core_terms)
        score += lexical_overlap_score(query, snippet)
        score += _pdf_passage_structure_bonus(query, page_text, snippet)
        candidates.append((
            score,
            page_number,
            snippet,
            _pdf_section_opening_priority(query, page_text),
        ))

    if not candidates:
        snippet = _best_snippet(query, pdf_text, max_chars=max_chars, max_segments=max_segments)
        if not snippet:
            return []
        return [(snippet, None, _snippet_score(query, snippet, core_terms))]

    candidates.sort(key=lambda item: item[0], reverse=True)
    selected: list[tuple[str, int | None, float]] = []
    opening_candidates = sorted(
        (candidate for candidate in candidates if candidate[3] > 0),
        key=lambda item: (item[3], item[0]),
        reverse=True,
    )
    reserved_openings = 2 if max_segments >= 5 else 1
    for score, page_number, snippet, _priority in opening_candidates[:reserved_openings]:
        compact = _compact_text(snippet, max_chars)
        if compact and not any(_similar_snippet(compact, existing) for existing, _page, _score in selected):
            selected.append((compact, page_number, score))

    for score, page_number, snippet, _priority in candidates:
        compact = _compact_text(snippet, max_chars)
        if not compact:
            continue
        if any(_similar_snippet(compact, existing) for existing, _page, _score in selected):
            continue
        selected.append((compact, page_number, score))
        if len(selected) >= max_segments:
            break
    return selected


def _pdf_section_opening_snippet_if_helpful(
    *,
    query: str,
    page_text: str,
    snippet: str,
    max_chars: int,
) -> str:
    body_text = _pdf_page_body_text(page_text)
    if not _looks_like_pdf_section_opening(body_text):
        return snippet
    meaningful_terms = _meaningful_query_terms(query)
    if meaningful_terms and _query_overlap_count(meaningful_terms, _text_tokens(body_text[:1600])) < 2:
        return snippet

    opening = _compact_text(body_text, max_chars)
    if not opening:
        return snippet
    if not snippet:
        return opening
    if _similar_snippet(opening[: min(len(opening), 1200)], snippet):
        return opening
    return opening


def _pdf_passage_structure_bonus(query: str, page_text: str, snippet: str) -> float:
    meaningful_terms = _meaningful_query_terms(query)
    if not meaningful_terms:
        return 0.0
    body_text = _pdf_page_body_text(page_text)
    overlap_count = _query_overlap_count(
        meaningful_terms,
        _text_tokens(f"{body_text[:1600]} {snippet[:800]}"),
    )
    if overlap_count < 2:
        return 0.0

    bonus = 0.0
    if _looks_like_pdf_section_opening(body_text):
        bonus += min(0.35, 0.08 + (0.04 * overlap_count))
    if _paragraph_contains_inline_list(snippet):
        bonus += 0.12
    return bonus


def _pdf_section_opening_priority(query: str, page_text: str) -> float:
    body_text = _pdf_page_body_text(page_text)
    if not _looks_like_pdf_section_opening(body_text):
        return 0.0
    meaningful_terms = _meaningful_query_terms(query)
    if not meaningful_terms:
        return 0.0
    leading = _compact_text(body_text, 700)
    overlap_count = _query_overlap_count(meaningful_terms, _text_tokens(leading))
    if overlap_count < 3:
        return 0.0
    priority = overlap_count / max(len(meaningful_terms), 1)
    if "overview" not in meaningful_terms and re.search(
        r"\b(?:chapter\s+one|overview|background)\b",
        leading.lower()[:260],
    ):
        priority *= 0.35
    return priority


def _pdf_page_body_text(page_text: str) -> str:
    compact = _compact_text(page_text, max(len(page_text), 1))
    if not compact:
        return ""
    return re.sub(
        r"^(?:JANUARY\s+2016\s+)?GUIDELINES\s+FOR\s+N?TEGRATED\s+MANAGEMENT\s+OF\s+ACUTE\s+MALNUTRITION\s+IN\s+UGANDA\s*\d+\s*(?:JANUARY\s+2016\s+)?",
        "",
        compact,
        count=1,
        flags=re.IGNORECASE,
    ).strip()


def _looks_like_pdf_section_opening(page_text: str) -> bool:
    leading = _compact_text(page_text, 900)
    if not leading:
        return False
    lowered = leading.lower()
    if _paragraph_looks_like_low_value_pdf_context(lowered):
        return False
    if re.search(r"\bchapter\s+(?:[a-z]+|\d+)\b", lowered):
        return True
    if re.search(r"\b(?:figure|table)\s+\d+\b", lowered[:320]):
        return False
    section_match = re.search(
        r"\b\d+(?:\.\d+){1,3}\s+[A-Z][A-Za-z][A-Za-z0-9 /,()&-]{8,}",
        leading,
    )
    if not section_match:
        return False
    preceding = leading[: section_match.start()]
    return not re.search(r"(?:^|\s)[-*•]\s+\S+", preceding)


def _compact_text(text: str, max_length: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_length:
        return compact
    return compact[: max_length - 3].rstrip() + "..."


def _read_pdf_text_cache(
    settings: EvidenceRetrievalSettings,
    url: str,
    *,
    allow_stale: bool = False,
) -> tuple[str, str, int, list[tuple[int, str]]] | None:
    cache_path = _pdf_text_cache_path(settings, url)
    if cache_path is None or not cache_path.exists():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        cache_version = int(payload.get("cache_version") or 0)
    except (TypeError, ValueError):
        return None
    if not MIN_PDF_TEXT_CACHE_VERSION <= cache_version <= PDF_TEXT_CACHE_VERSION:
        return None
    fetched_at = float(payload.get("fetched_at") or 0.0)
    ttl = max(settings.crawl_cache_ttl_seconds, 0)
    if ttl and not allow_stale and time.time() - fetched_at > ttl:
        return None
    text = str(payload.get("text") or "")
    final_url = str(payload.get("final_url") or url)
    pages_extracted = int(payload.get("pages_extracted") or 0)
    if not text:
        return None
    page_texts: list[tuple[int, str]] = []
    raw_pages = payload.get("page_texts")
    if isinstance(raw_pages, list):
        for entry in raw_pages:
            if isinstance(entry, dict):
                raw_page_number = entry.get("page_number")
                raw_page_text = entry.get("text")
            elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
                raw_page_number = entry[0]
                raw_page_text = entry[1]
            else:
                continue
            try:
                page_number = int(raw_page_number or 0)
            except (TypeError, ValueError):
                continue
            page_text = str(raw_page_text or "")
            if page_number > 0 and page_text:
                page_texts.append((page_number, page_text))
    return final_url, text, pages_extracted, page_texts


def _write_pdf_text_cache(
    settings: EvidenceRetrievalSettings,
    original_url: str,
    final_url: str,
    text: str,
    pages_extracted: int,
    page_texts: list[tuple[int, str]],
) -> None:
    cache_path = _pdf_text_cache_path(settings, original_url)
    if cache_path is None:
        return
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(
                {
                    "cache_version": PDF_TEXT_CACHE_VERSION,
                    "original_url": original_url,
                    "final_url": final_url,
                    "fetched_at": time.time(),
                    "pages_extracted": pages_extracted,
                    "text": text[:MAX_PDF_TEXT_CHARS],
                    "page_texts": [
                        {"page_number": page_number, "text": page_text}
                        for page_number, page_text in page_texts
                    ],
                }
            ),
            encoding="utf-8",
        )
    except OSError:
        logger.debug("could not write PDF text cache for %s", original_url, exc_info=True)


def _pdf_text_cache_path(settings: EvidenceRetrievalSettings, url: str) -> Path | None:
    cache_path = _static_cache_path(settings, url)
    return cache_path.with_suffix(".pdftext.json") if cache_path is not None else None


def _read_static_cache(
    settings: EvidenceRetrievalSettings,
    url: str,
    *,
    allow_stale: bool = False,
) -> dict[str, object] | None:
    cache_path = _static_cache_path(settings, url)
    if cache_path is None or not cache_path.exists():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    fetched_at = float(payload.get("fetched_at") or 0.0)
    ttl = max(settings.crawl_cache_ttl_seconds, 0)
    if ttl and not allow_stale and time.time() - fetched_at > ttl:
        return None
    if not payload.get("html"):
        return None
    return payload


def _write_static_cache(
    settings: EvidenceRetrievalSettings,
    original_url: str,
    final_url: str,
    content_type: str,
    html: str,
) -> None:
    cache_path = _static_cache_path(settings, original_url)
    if cache_path is None:
        return
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(
                {
                    "original_url": original_url,
                    "final_url": final_url,
                    "content_type": content_type,
                    "fetched_at": time.time(),
                    "html": html,
                }
            ),
            encoding="utf-8",
        )
    except OSError:
        logger.debug("could not write static crawl cache for %s", original_url, exc_info=True)


def _static_cache_path(settings: EvidenceRetrievalSettings, url: str) -> Path | None:
    if settings.crawl_cache_ttl_seconds < 0:
        return None
    cache_dir = (
        Path(settings.crawl_cache_dir)
        if settings.crawl_cache_dir
        else Path(__file__).resolve().parents[4] / "logs" / "evidence-cache"
    )
    key = hashlib.sha256(_canonical_url(url).encode("utf-8")).hexdigest()
    return cache_dir / f"{key}.json"


def _items_cover_query_topic(query: str, items: list[EvidenceItem]) -> bool:
    return any(
        _content_matches_core_query(
            query,
            item.title,
            str(item.url),
            item.snippet or item.abstract or "",
        )
        for item in items
    )


def _content_matches_core_query(
    query: str,
    title: str,
    url: str,
    snippet: str,
    focus_terms: set[str] | None = None,
) -> bool:
    core_terms = focus_terms or _core_query_terms(query)
    if not core_terms:
        return True
    text = f"{title} {url} {snippet}"
    tokens = _text_tokens(text)
    if focus_terms:
        query_terms = _core_query_terms(query)
        if _query_overlap_count(focus_terms, tokens) < 1:
            return False
        if query_terms:
            return _query_overlap_count(query_terms, tokens) >= _required_query_overlap(query_terms)
        return True
    required_overlap = _required_query_overlap(core_terms)
    return _query_overlap_count(core_terms, tokens) >= required_overlap


def _source_selection_terms(query: str, sources: list[CrawlSource]) -> set[str]:
    query_terms = _core_query_terms(query)
    if not query_terms or not sources:
        return query_terms
    source_token_sets = [_text_tokens(" ".join(source.topics)) for source in sources]
    term_frequencies = {
        term: _source_term_frequency(term, source_token_sets)
        for term in query_terms
    }
    catalog_terms = {
        term
        for term, frequency in term_frequencies.items()
        if frequency > 0
    }
    max_shared_frequency = max(1, len(source_token_sets) // 4)
    distinctive_terms = {
        term
        for term in catalog_terms
        if term_frequencies[term] <= max_shared_frequency
    }
    return distinctive_terms or catalog_terms or query_terms


def _source_selection_text(source: CrawlSource) -> str:
    return f"{source.name} {source.publisher} {' '.join(source.topics)}"


def _source_term_frequency(term: str, source_token_sets: list[set[str]]) -> int:
    return sum(1 for tokens in source_token_sets if _term_matches_tokens(term, tokens))


def _source_topic_signal(query_terms: set[str], source: CrawlSource) -> float:
    if not query_terms:
        return 0.0
    return _source_topic_match_count(query_terms, source) / len(query_terms)


def _source_topic_match_count(query_terms: set[str], source: CrawlSource) -> int:
    if not query_terms:
        return 0
    source_tokens = _text_tokens(" ".join(source.topics))
    return sum(
        1
        for term in query_terms
        if _term_matches_tokens(term, source_tokens)
    )


def _source_is_catalog_broad(source: CrawlSource) -> bool:
    return any(topic.strip().lower() == "all diseases" for topic in source.topics)


def _title_hint(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.strip("/").split("/")[-1]
    title = path.replace("-", " ").replace("_", " ").replace(".html", "").replace(".pdf", "")
    return title.title() or parsed.netloc


def _canonical_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed._replace(fragment="").geturl()


def _is_probable_pdf(url: str) -> bool:
    return urlparse(url).path.lower().endswith(".pdf")


def _is_search_like_url(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    query = parsed.query.lower()
    path_segments = {segment for segment in path.split("/") if segment}
    if path_segments.intersection({"search", "discover", "results"}):
        return True
    if path.endswith("/search") or "/search/" in path:
        return True
    return any(
        marker in query
        for marker in ("q=", "query=", "search=", "searchquery=", "keywords=", "term=", "s=")
    )


def _is_trusted_guideline_url(url: str) -> bool:
    host = urlparse(url).netloc.lower().replace("www.", "")
    return any(
        host == domain or host.endswith(f".{domain}")
        for domain in (
            "afro.who.int",
            "health.go.ug",
            "iris.who.int",
            "medicalguidelines.msf.org",
            "nice.org.uk",
            "platform.who.int",
            "who.int",
        )
    )


def _generic_url_penalty(url: str) -> float:
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if not path or path.lower() in {"books", "resources", "publication", "downloads"}:
        return 0.05
    return 0.0


def _query_topic_bonus(query: str, url: str) -> float:
    core_terms = _core_query_terms(query)
    if not core_terms:
        return 0.0
    tokens = _text_tokens(f"{url} {_title_hint(url)}")
    matches = sum(1 for term in core_terms if _term_matches_tokens(term, tokens))
    return min(matches * 0.12, 0.36)


def _core_url_bonus(query: str, url: str) -> float:
    haystack = f"{url} {_title_hint(url)}".lower()
    core_terms = _core_query_terms(query)
    if not core_terms:
        return 0.0
    tokens = _text_tokens(haystack)
    matches = sum(1 for term in core_terms if _term_matches_tokens(term, tokens))
    return min(matches * 0.08, 0.24)


def _core_query_terms(query: str) -> set[str]:
    return _text_tokens(query)


def _meaningful_query_terms(query: str) -> set[str]:
    return {token for token in _text_tokens(query) if token not in GENERAL_QUERY_STOPWORDS}


def _text_tokens(value: str) -> set[str]:
    normalized = re.sub(r"(?<=\w)[-‐‑‒–—](?=\w)", "", value.lower())
    return {
        token
        for token in re.sub(r"[^a-zA-Z0-9\s]", " ", normalized).split()
        if len(token) > 1 and not token.isdigit()
    }


def _term_matches_tokens(term: str, tokens: set[str]) -> bool:
    return any(_terms_match(term, token) for token in tokens)


def _query_overlap_count(query_terms: set[str], text_tokens: set[str]) -> int:
    return sum(1 for term in query_terms if _term_matches_tokens(term, text_tokens))


def _required_query_overlap(query_terms: set[str]) -> int:
    if len(query_terms) <= 3:
        return 1
    if len(query_terms) <= 6:
        return 2
    return min(3, len(query_terms))


def _terms_match(left: str, right: str) -> bool:
    if left == right:
        return True
    shorter, longer = (left, right) if len(left) <= len(right) else (right, left)
    if len(shorter) >= 6 and len(shorter) / max(len(longer), 1) >= 0.75:
        return longer.startswith(shorter)
    return False


def _html_title(html: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return _clean_html_text(match.group(1))


def _html_to_text(html: str) -> str:
    cleaned = re.sub(r"(?is)<(script|style|noscript|svg|header|footer|nav)[^>]*>.*?</\1>", " ", html)
    cleaned = re.sub(r"(?i)<br\s*/?>", "\n", cleaned)
    cleaned = re.sub(r"(?i)</(p|div|li|h1|h2|h3|h4|tr)>", "\n", cleaned)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = _clean_html_text(cleaned)
    return re.sub(r"\n{3,}", "\n\n", cleaned)


def _extract_html_links(html: str, base_url: str) -> list[tuple[str, str]]:
    parser = _HTMLLinkExtractor(base_url)
    try:
        parser.feed(html)
    except Exception:
        return []
    return parser.links


class _HTMLLinkExtractor(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[tuple[str, str]] = []
        self._href_stack: list[str | None] = []
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = next((value for key, value in attrs if key.lower() == "href"), None)
        absolute_url = urljoin(self.base_url, str(href or "")).split("#", 1)[0]
        if not absolute_url.startswith(("http://", "https://")):
            absolute_url = ""
        self._href_stack.append(absolute_url or None)
        self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._href_stack:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self._href_stack:
            return
        href = self._href_stack.pop()
        text = _clean_html_text(" ".join(self._text_parts))
        self._text_parts = []
        if href:
            self.links.append((href, text))


def _clean_html_text(value: str) -> str:
    replacements = {
        "&nbsp;": " ",
        "&amp;": "&",
        "&lt;": "<",
        "&gt;": ">",
        "&quot;": '"',
        "&#39;": "'",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    lines = [re.sub(r"\s+", " ", line).strip() for line in value.splitlines()]
    return "\n".join(line for line in lines if line)


def _result_title(result: object) -> str | None:
    for attr in ("title", "metadata"):
        value = getattr(result, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            title = value.get("title")
            if isinstance(title, str) and title.strip():
                return title.strip()
    return None


def _markdown_text(result: object) -> str:
    markdown = getattr(result, "markdown", None)
    if markdown is None:
        return ""
    if isinstance(markdown, str):
        return markdown
    for attr in ("fit_markdown", "markdown_with_citations", "raw_markdown"):
        value = getattr(markdown, attr, None)
        if isinstance(value, str) and value.strip():
            return value
    return str(markdown)


def _extract_links(result: object, base_url: str) -> list[tuple[str, str]]:
    links = getattr(result, "links", None)
    if not isinstance(links, dict):
        return []

    extracted: list[tuple[str, str]] = []
    for group in ("internal", "external"):
        values = links.get(group, [])
        if not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, dict):
                continue
            href = item.get("href") or item.get("url")
            if not href:
                continue
            text = str(item.get("text") or item.get("title") or "").strip()
            absolute_url = urljoin(base_url, str(href)).split("#", 1)[0]
            if absolute_url.startswith(("http://", "https://")):
                extracted.append((absolute_url, text))
    return extracted


def _evidence_type(url: str, title: str, markdown: str) -> str:
    return "clinical_resource"


def _content_results(results: list[tuple[CrawlTarget, object]]) -> list[tuple[CrawlTarget, object]]:
    return [(target, result) for target, result in results if not target.is_search_page]


def _dedupe_targets(targets: list[CrawlTarget]) -> list[CrawlTarget]:
    seen: set[str] = set()
    deduped: list[CrawlTarget] = []
    for target in targets:
        key = _canonical_url(target.url)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(target)
    return deduped


def _dedupe_items(items: list[EvidenceItem]) -> list[EvidenceItem]:
    seen: set[str] = set()
    deduped: list[EvidenceItem] = []
    for item in items:
        key = _item_passage_key(item)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _item_passage_key(item: EvidenceItem) -> str:
    raw = item.raw if isinstance(item.raw, dict) else {}
    passage_id = str(raw.get("passage_id") or "").strip()
    if passage_id:
        return f"passage:{passage_id}"
    section = " ".join(
        str(part)
        for part in (
            raw.get("page_start"),
            raw.get("page_label"),
            raw.get("section_title"),
            raw.get("section"),
            raw.get("heading"),
        )
        if part
    )
    text = " ".join(part for part in (item.abstract or "", item.snippet or "") if part)
    fingerprint = hashlib.sha1(
        re.sub(r"\s+", " ", text.lower()).strip()[:1000].encode()
    ).hexdigest()[:16] if text else ""
    normalized_section = re.sub(r"\s+", " ", section.lower()).strip()
    return "|".join(
        part
        for part in (
            f"url:{_canonical_url(str(item.url))}",
            f"section:{normalized_section}" if normalized_section else "",
            f"text:{fingerprint}" if fingerprint else "",
        )
        if part
    )


def _remaining_seconds(deadline: float) -> float:
    return max(deadline - time.perf_counter(), 0.0)


def _initial_search_timeout(remaining_seconds: float, has_seed_fallback: bool) -> float:
    if remaining_seconds <= 0:
        return 0.0
    if not has_seed_fallback:
        return remaining_seconds
    return min(remaining_seconds, max(remaining_seconds * 0.65, 2.0))


def _best_snippet(
    query: str,
    markdown: str,
    max_chars: int = 1200,
    max_segments: int = 2,
) -> str:
    lines = [part.strip() for part in re.split(r"\n+", markdown) if part.strip()]
    if not lines:
        return markdown[:max_chars]
    paragraphs: list[str] = []
    for index, line in enumerate(lines):
        if len(line) < 40:
            continue
        start = _snippet_context_start(lines, index)
        end = _snippet_context_end(lines, index)
        paragraphs.append(" ".join(lines[start:end]))
    if not paragraphs:
        paragraphs = lines
    lower_markdown = markdown.lower()
    core_terms = _core_query_terms(query)
    for term in sorted(core_terms, key=len, reverse=True):
        if len(term) < 4:
            continue
        window_chars = min(max_chars, 1100)
        for match in re.finditer(re.escape(term), lower_markdown):
            before_chars = min(650, max(window_chars // 2, 350))
            start = max(match.start() - before_chars, 0)
            end = min(start + window_chars, len(markdown))
            end = _extend_window_for_following_list(markdown, start, end, max_extra=700)
            paragraphs.append(markdown[start:end])
            if len(paragraphs) > 80:
                break
    useful_paragraphs = [
        paragraph
        for paragraph in paragraphs
        if not _paragraph_looks_like_low_value_pdf_context(paragraph.lower())
    ]
    if useful_paragraphs:
        paragraphs = useful_paragraphs
    candidates = [
        (
            _snippet_score(query, paragraph, core_terms),
            paragraph,
            _text_tokens(paragraph),
        )
        for paragraph in paragraphs
    ]
    selected: list[str] = []
    covered_terms: set[str] = set()
    while candidates and len(selected) < max_segments:
        candidates.sort(
            key=lambda candidate: (
                candidate[0]
                + 0.35
                * len(
                    {
                        term
                        for term in core_terms
                        if term not in covered_terms
                        and _term_matches_tokens(term, candidate[2])
                    }
                )
            ),
            reverse=True,
        )
        _, paragraph, tokens = candidates.pop(0)
        snippet = " ".join(paragraph.split())
        if not snippet:
            continue
        if any(_similar_snippet(snippet, existing) for existing in selected):
            continue
        selected.append(snippet)
        covered_terms.update(
            term
            for term in core_terms
            if _term_matches_tokens(term, tokens)
        )
    if not selected:
        return ""
    return " ... ".join(selected)[:max_chars]


def _snippet_context_start(lines: list[str], index: int) -> int:
    if index > 0 and _paragraph_looks_like_low_value_pdf_context(lines[index - 1].lower()):
        return index
    if not lines[index].rstrip().endswith(":"):
        return max(index - 1, 0)
    return max(index - 2, 0)


def _snippet_context_end(lines: list[str], index: int) -> int:
    end = min(index + 2, len(lines))
    if not lines[index].rstrip().endswith(":"):
        return end
    saw_list_line = False
    for next_index in range(index + 1, min(index + 8, len(lines))):
        next_line = lines[next_index].strip()
        if not next_line:
            break
        if saw_list_line and _looks_like_new_numbered_section(next_line):
            break
        if _looks_like_continuation_list_line(next_line):
            end = next_index + 1
            saw_list_line = True
            if re.search(r"\b(?:certainty|quality)\s+evidence\b", next_line, flags=re.IGNORECASE):
                break
            continue
        if next_index == index + 1:
            end = next_index + 1
            continue
        break
    return end


def _extend_window_for_following_list(text: str, start: int, end: int, max_extra: int) -> int:
    lookaround = text[max(start, end - 220): min(len(text), end + 120)]
    if not re.search(r":\s*(?:\n\s*)?(?:\d+[\).]|[-*•])\s+", lookaround):
        if not text[start:end].rstrip().endswith(":"):
            return end
    return min(len(text), end + max_extra)


def _looks_like_continuation_list_line(line: str) -> bool:
    return bool(
        re.match(r"^(?:\d+[\).]|[-*•])\s+", line)
        or re.match(r"^[A-Z][A-Za-z0-9+/-]{1,12}(?:\s|$)", line)
        and len(line) < 140
    )


def _looks_like_new_numbered_section(line: str) -> bool:
    return bool(re.match(r"^\d+\.\s+[A-Z][A-Z\s-]{6,}", line))


def _snippet_score(query: str, paragraph: str, core_terms: set[str]) -> float:
    tokens = _text_tokens(paragraph)
    overlap_count = _query_overlap_count(core_terms, tokens)
    coverage = overlap_count / max(len(core_terms), 1)
    density = overlap_count / max(len(tokens), 1)
    score = lexical_overlap_score(query, paragraph) + (0.25 * coverage) + (0.1 * density)
    paragraph_text = paragraph.lower()
    if _paragraph_contains_inline_list(paragraph):
        score += 0.6
    # A page that states doses, thresholds, frequencies or durations is more use
    # at the bedside than one that only names the pathway. Both mention the
    # condition, so lexical overlap cannot separate them.
    score += 0.45 * clinical_specificity_score(paragraph)
    if _paragraph_looks_like_low_value_pdf_context(paragraph_text):
        score -= 0.6
    return score


def _paragraph_contains_inline_list(paragraph: str) -> bool:
    ordered_markers = [
        int(match.group(1))
        for match in re.finditer(r"(?:^|\s)(\d{1,2})[\).]\s+\S+", paragraph)
    ]
    has_ordered_list = any(
        current == previous + 1
        for previous, current in zip(ordered_markers, ordered_markers[1:])
    )
    has_bullet_list = len(re.findall(r"(?:^|\s)[-*•]\s+\S+", paragraph)) >= 2
    return has_ordered_list or has_bullet_list


def _paragraph_looks_like_low_value_pdf_context(paragraph_text: str) -> bool:
    if paragraph_text.count(".....") >= 2:
        return True
    if re.search(r"\b(table of contents|contents|list of tables|list of figures|references|bibliography)\b", paragraph_text):
        return True
    if re.search(r"\b(acknowledgements?|guideline development group|contributors?|working group members)\b", paragraph_text):
        return True
    if "doi:" in paragraph_text or "doi.org/" in paragraph_text:
        return True
    year_count = len(re.findall(r"\b(?:19|20)\d{2}\b", paragraph_text))
    if year_count >= 2 and re.search(r"\b(et al|geneva|journal|bibliography|guideline:)\b", paragraph_text):
        return True
    if year_count >= 1 and re.search(r"\b(et al|journal|study group)\b", paragraph_text):
        return True
    return False


def _similar_snippet(left: str, right: str) -> bool:
    left_text = left.lower()
    right_text = right.lower()
    if left_text in right_text or right_text in left_text:
        return True
    left_tokens = _text_tokens(left_text)
    right_tokens = _text_tokens(right_text)
    if not left_tokens or not right_tokens:
        return False
    overlap = len(left_tokens.intersection(right_tokens))
    return overlap / min(len(left_tokens), len(right_tokens)) > 0.72
