from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus, urljoin, urlparse

import httpx

from evidence_retrieval_test.src.config import EvidenceRetrievalSettings
from evidence_retrieval_test.src.models import EvidenceItem, EvidenceSource
from evidence_retrieval_test.src.providers.base import BaseEvidenceProvider, ProviderError
from evidence_retrieval_test.src.services.evidence_ranker import keyword_overlap_score

logger = logging.getLogger(__name__)


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


class Crawl4AIProvider(BaseEvidenceProvider):
    source_name = EvidenceSource.CRAWL4AI.value

    def __init__(
        self,
        settings: EvidenceRetrievalSettings,
        sources: list[CrawlSource] | None = None,
    ) -> None:
        super().__init__(settings)
        self.sources = sources or load_crawl_sources(settings)

    def search(self, query: str, max_results: int) -> list[EvidenceItem]:
        if not self.settings.enable_crawl4ai:
            return []

        selected_sources = self._select_sources(query)
        if not selected_sources:
            return []

        started_at = time.perf_counter()
        deadline = started_at + self.settings.crawl_time_budget_seconds
        pdf_items = self._pdf_seed_items(query, selected_sources, max_results)
        static_items = (
            self._static_seed_items(
                query,
                selected_sources,
                max_results,
                deadline,
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

    def _select_sources(self, query: str) -> list[CrawlSource]:
        query_text = query.lower()
        scored: list[tuple[float, CrawlSource]] = []
        for source in self.sources:
            if not any(self._is_allowed_domain(domain) for domain in source.domains):
                continue
            topic_text = " ".join(
                (
                    *source.topics,
                    source.name,
                    source.publisher,
                )
            )
            overlap = keyword_overlap_score(query, topic_text)
            named_source_bonus = 0.35 if any(part in query_text for part in _source_aliases(source)) else 0.0
            uganda_bonus = 0.18 if "uganda" in query_text and any("uganda" in topic for topic in source.topics) else 0.0
            broad_guideline_bonus = 0.08 if _is_broad_guideline_source(source) else 0.0
            score = overlap + named_source_bonus + uganda_bonus + broad_guideline_bonus + (source.priority * 0.12)
            scored.append((score, source))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [source for _, source in scored[: self.settings.crawl_max_sources]]

    async def _crawl_for_query(
        self,
        query: str,
        sources: list[CrawlSource],
        max_results: int,
        deadline: float,
    ) -> list[EvidenceItem]:
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
                    keyword_overlap_score(
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
                if self._is_allowed_url(url) and _is_broad_seed_url(url)
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
    ) -> list[EvidenceItem]:
        scored_targets: list[tuple[float, CrawlTarget]] = []
        first_targets: list[CrawlTarget] = []
        for source in sources:
            source_seed_scores = [
                (score, url)
                for score, url in self._scored_seed_urls(query, source)[:5]
                if not _is_probable_pdf(url)
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
        targets = _dedupe_targets(
            [*first_targets, *[target for _, target in scored_targets]]
        )[: min(self.settings.crawl_max_pages, max_results + 6)]
        timeout = min(float(self.settings.request_timeout_seconds), 4.0, _remaining_seconds(deadline))
        if timeout <= 0.25:
            return []
        with ThreadPoolExecutor(max_workers=min(6, max(len(targets), 1))) as executor:
            futures = {
                executor.submit(_fetch_static_target, query, target, timeout): target
                for target in targets
            }
            items = []
            for future in as_completed(futures):
                item = future.result()
                if item is not None:
                    items.append(item)
        items.sort(key=lambda item: item.relevance_score or 0.0, reverse=True)
        return items[:max_results]

    def _pdf_seed_items(
        self,
        query: str,
        sources: list[CrawlSource],
        max_results: int,
    ) -> list[EvidenceItem]:
        items: list[EvidenceItem] = []
        for source in sources:
            scored_urls = [
                (
                    keyword_overlap_score(
                        query,
                        f"{source.name} {source.publisher} {' '.join(source.topics)} {_title_hint(url)} {url}",
                    )
                    + _query_topic_bonus(query, url)
                    + _core_url_bonus(query, url)
                    + (source.priority * 0.18),
                    url,
                )
                for url in source.seed_urls
            ]
            for score, url in sorted(scored_urls, reverse=True):
                if not _is_probable_pdf(url) or not self._is_allowed_url(url):
                    continue
                title = _title_hint(url)
                evidence_text = f"{source.name} {source.publisher} {' '.join(source.topics)} {title} {url}"
                relevance = max(keyword_overlap_score(query, evidence_text), score)
                if relevance < 0.08 or not _content_matches_core_query(query, title, url, evidence_text):
                    continue
                items.append(
                    EvidenceItem(
                        id=f"crawl4ai:{_canonical_url(url)}",
                        source=EvidenceSource.CRAWL4AI,
                        title=title,
                        snippet=(
                            f"{source.name} from {source.publisher}. "
                            f"Approved guideline catalogue PDF. Topics: {', '.join(source.topics[:12])}."
                        ),
                        authors=[],
                        journal_or_publisher=source.publisher,
                        url=url,
                        full_text_url=url,
                        open_access=True,
                        evidence_type="guideline",
                        relevance_score=round(relevance, 4),
                        raw={
                            "source_name": source.name,
                            "retrieval_mode": "pdf_seed_metadata",
                        },
                    )
                )
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
                link_score = keyword_overlap_score(query, f"{link_text} {link_url} {source.name} {source.publisher}")
                if _looks_like_clinical_document(link_url, link_text):
                    link_score += 0.16
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
            if not _content_matches_core_query(query, target.title_hint, target.url, snippet):
                continue
            relevance = keyword_overlap_score(query, f"{target.title_hint} {snippet}")
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


def _source_aliases(source: CrawlSource) -> tuple[str, ...]:
    name = source.name.lower()
    aliases = [name, source.publisher.lower()]
    if "world health organization" in name:
        aliases.extend(["who", "w.h.o"])
    if "regional office for africa" in name or "afro" in source.publisher.lower():
        aliases.extend(["who afro", "afro"])
    if "centers for disease" in name or source.publisher.lower() == "cdc":
        aliases.append("cdc")
    if "uganda" in name or "uganda" in source.publisher.lower():
        aliases.extend(["uganda", "moh", "ministry of health"])
    if "infectious diseases institute" in name:
        aliases.extend(["idi", "idi uganda"])
    if "kenya" in name:
        aliases.extend(["kenya", "moh kenya"])
    if "tanzania" in name:
        aliases.extend(["tanzania", "nmcp"])
    if "clinicalinfo" in name:
        aliases.extend(["nih", "clinicalinfo"])
    return tuple(aliases)


def _source_for_url(url: str, by_domain: dict[str, CrawlSource]) -> CrawlSource | None:
    host = urlparse(url).netloc.lower().replace("www.", "")
    for domain, source in by_domain.items():
        if host == domain or host.endswith(f".{domain}"):
            return source
    return None


def _fetch_static_target(query: str, target: CrawlTarget, timeout: float) -> EvidenceItem | None:
    headers = {"User-Agent": "EmpiricoEvidenceRetrieval/0.1"}
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
            response = client.get(target.url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.debug("static guideline fetch failed for %s: %s", target.url, exc)
        return None

    content_type = response.headers.get("content-type", "").lower()
    if "text/html" not in content_type and "application/xhtml" not in content_type:
        return None
    markdown = _html_to_text(response.text)
    if len(markdown) < 120:
        return None
    snippet = _best_snippet(query, markdown)
    if not _content_matches_core_query(query, target.title_hint, str(response.url), snippet):
        return None
    relevance = keyword_overlap_score(query, f"{target.title_hint} {snippet}")
    if relevance < 0.08:
        return None
    return EvidenceItem(
        id=f"crawl4ai:{_canonical_url(str(response.url))}",
        source=EvidenceSource.CRAWL4AI,
        title=_html_title(response.text) or target.title_hint,
        abstract=None,
        snippet=snippet,
        authors=[],
        journal_or_publisher=target.publisher,
        url=str(response.url),
        full_text_url=str(response.url),
        open_access=True,
        evidence_type=_evidence_type(str(response.url), target.title_hint, markdown),
        relevance_score=round(relevance, 4),
        raw={
            "source_name": target.source_name,
            "retrieval_mode": "static_html",
            "markdown_preview": markdown[:4000],
        },
    )


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


def _content_matches_core_query(query: str, title: str, url: str, snippet: str) -> bool:
    core_terms = _core_query_terms(query)
    if not core_terms:
        return True
    tokens = _text_tokens(f"{title} {url} {snippet}")
    return _query_overlap_count(core_terms, tokens) >= _required_query_overlap(core_terms)


def _is_broad_guideline_source(source: CrawlSource) -> bool:
    haystack = f"{source.name} {source.publisher} {' '.join(source.topics)}".lower()
    return any(
        term in haystack
        for term in (
            "all diseases",
            "clinical guideline",
            "guidelines",
            "medical guideline",
            "bookshelf",
            "pocket book",
        )
    )


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


def _is_broad_seed_url(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.strip("/").lower()
    if not path:
        return True

    generic_segments = {
        "book",
        "books",
        "clinical-recommendations.html",
        "document",
        "documents",
        "download",
        "downloads",
        "guidance",
        "guidelines",
        "publication",
        "publications",
        "practice-guideline",
        "resource",
        "resources",
        "search",
    }
    ignored_segments = {"en", "web", "index.html", "home"}
    segments = [segment for segment in path.split("/") if segment and segment not in ignored_segments]
    if not segments:
        return True
    return bool(segments) and all(segment in generic_segments for segment in segments)


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


def _text_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.sub(r"[^a-zA-Z0-9\s]", " ", value.lower()).split()
        if len(token) > 1 and not token.isdigit()
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


def _looks_like_clinical_document(url: str, text: str) -> bool:
    haystack = f"{url} {text}".lower()
    if any(term in haystack for term in ("privacy", "cookie", "terms-of-use", "terms of use")):
        return False
    return any(
        term in haystack
        for term in (
            "assessment",
            "care",
            "condition",
            "diagnosis",
            "disease",
            "emergency",
            "guideline",
            "guidance",
            "handbook",
            "injury",
            "manual",
            "medicine",
            "policy",
            "procedure",
            "protocol",
            "clinical",
            "referral",
            "recommendation",
            "surgery",
            "symptom",
            "therapy",
            "treatment",
            "trauma",
            ".pdf",
        )
    )


def _evidence_type(url: str, title: str, markdown: str) -> str:
    haystack = f"{url} {title} {markdown[:1000]}".lower()
    if any(term in haystack for term in ("guideline", "guidance", "recommendation", "manual", "handbook")):
        return "guideline"
    if "systematic review" in haystack or "meta-analysis" in haystack:
        return "systematic_review"
    if "trial" in haystack or "randomized" in haystack:
        return "clinical_trial"
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
        key = _canonical_url(str(item.url))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _remaining_seconds(deadline: float) -> float:
    return max(deadline - time.perf_counter(), 0.0)


def _initial_search_timeout(remaining_seconds: float, has_seed_fallback: bool) -> float:
    if remaining_seconds <= 0:
        return 0.0
    if not has_seed_fallback:
        return remaining_seconds
    return min(remaining_seconds, max(remaining_seconds * 0.65, 2.0))


def _best_snippet(query: str, markdown: str, max_chars: int = 1200) -> str:
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", markdown) if part.strip()]
    if not paragraphs:
        return markdown[:max_chars]
    scored = sorted(
        paragraphs,
        key=lambda paragraph: keyword_overlap_score(query, paragraph),
        reverse=True,
    )
    snippet = scored[0]
    return snippet[:max_chars]
