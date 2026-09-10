import asyncio
import json
import os
import re
import threading
import time

import pytest

from healthnavi.evidence_retrieval.config import EvidenceRetrievalSettings, get_settings
from healthnavi.evidence_retrieval.models import EvidenceItem, EvidenceSource
from healthnavi.evidence_retrieval.providers import crawl4ai_provider as crawl_provider_module
from healthnavi.evidence_retrieval.providers.crawl4ai_provider import (
    Crawl4AIProvider,
    CrawlSource,
    _best_static_item_for_query,
    _best_snippet,
    _content_matches_core_query,
    _pdf_text_cache_path,
    _read_pdf_text_cache,
    _read_static_cache,
    load_crawl_sources,
    _source_selection_terms,
    _write_static_cache,
)
from healthnavi.evidence_retrieval.providers.official_health_api_provider import (
    _query_tokens as _official_health_api_query_tokens,
)
from healthnavi.evidence_retrieval.services.evidence_ranker import (
    deduplicate_items,
    rank_evidence_items,
)
from healthnavi.evidence_retrieval.services.query_builder import (
    build_provider_query,
    build_query_plan,
)
from healthnavi.evidence_retrieval.services.evidence_policy import (
    evidence_policy_sort_key,
)
from healthnavi.evidence_retrieval.services.evidence_search_service import EvidenceSearchService
from healthnavi.services.evidence_retrieval_adapter import (
    AnswerGenerationError,
    _active_source_preference_terms,
    _answer_looks_like_service_status,
    _answer_top_k,
    _citations_from_evidence,
    _country_code_for_retrieval_query,
    _evidence_request_plan_for_request,
    _evidence_country_code_for_search,
    _evidence_search_top_k,
    _filter_evidence_items,
    _local_followup_questions,
    _local_evidence_provider_mode,
    _max_output_tokens_for_mode,
    _merge_evidence_items,
    _model_timeout_for_mode,
    _normalize_model_service_response,
    _query_focused_snippet,
    _rescue_evidence_search,
    _retrieval_planner_enabled,
    _retrieval_queries_for_request,
    _search_settings_for_mode,
    _search_retrieval_queries,
    _source_preference_terms,
    _unique_evidence_passages,
    generate_model_service_response,
)


def _catalog_source_text(source: CrawlSource) -> str:
    return " ".join(
        (
            source.name,
            source.publisher,
            " ".join(source.domains),
            " ".join(source.topics),
            " ".join(source.seed_urls),
            " ".join(source.search_urls),
        )
    ).lower()


def _catalog_source_is_uganda(source: CrawlSource) -> bool:
    text = _catalog_source_text(source)
    return (
        "uganda" in text
        or "health.go.ug" in text
        or "library.health.go.ug" in text
        or "nda.or.ug" in text
        or "uniph.go.ug" in text
        or "cphl.go.ug" in text
        or "qadash.cphl.go.ug" in text
        or "uci.or.ug" in text
        or "ulii.org" in text
        or "idi.mak.ac.ug" in text
        or "elearning.idi.co.ug" in text
    )


def _catalog_source_mentions(source: CrawlSource, *terms: str) -> bool:
    text = _catalog_source_text(source)
    return any(term.lower() in text for term in terms)


def _catalog_domains(sources: list[CrawlSource]) -> list[str]:
    domains: list[str] = []
    for source in sources:
        for domain in source.domains:
            if domain not in domains:
                domains.append(domain)
    return domains


def test_local_provider_env_vars_are_read_by_empirico(monkeypatch):
    monkeypatch.setenv("NCBI_API_KEY", "local-ncbi-key")
    monkeypatch.setenv("NCBI_TOOL_EMAIL", "clinician@example.org")
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "local-semantic-key")
    monkeypatch.setenv("ENABLE_PUBMED", "true")
    monkeypatch.setenv("ENABLE_EUROPE_PMC", "true")
    monkeypatch.setenv("ENABLE_SEMANTIC_SCHOLAR", "true")
    monkeypatch.setenv("ENABLE_OFFICIAL_HEALTH_APIS", "true")
    monkeypatch.setenv("ENABLE_CRAWL4AI", "true")
    monkeypatch.setenv("ENABLE_CRAWL4AI_BROWSER", "false")
    monkeypatch.setenv("CRAWL_ALLOWED_DOMAINS", "health.go.ug,who.int,ncbi.nlm.nih.gov")
    monkeypatch.setenv("CRAWL_CACHE_DIR", "/tmp/empirico-test-cache")
    monkeypatch.setenv("CRAWL_CACHE_TTL_SECONDS", "604800")
    monkeypatch.setenv("CRAWL_MAX_SOURCES", "8")
    monkeypatch.setenv("CRAWL_MAX_PAGES", "14")
    monkeypatch.setenv("CRAWL_TIME_BUDGET_SECONDS", "8")
    monkeypatch.setenv("RETRIEVAL_TIME_BUDGET_SECONDS", "10")
    get_settings.cache_clear()

    settings = get_settings()
    provider_names = [
        provider.source_name
        for provider in EvidenceSearchService(settings=settings, provider_mode="web").providers
    ]
    get_settings.cache_clear()

    assert settings.ncbi_api_key == "local-ncbi-key"
    assert settings.ncbi_tool_email == "clinician@example.org"
    assert settings.semantic_scholar_api_key == "local-semantic-key"
    assert settings.crawl_allowed_domains == [
        "health.go.ug",
        "who.int",
        "ncbi.nlm.nih.gov",
    ]
    assert settings.crawl_cache_dir == "/tmp/empirico-test-cache"
    assert settings.crawl_cache_ttl_seconds == 604800
    assert settings.crawl_max_sources == 8
    assert settings.crawl_max_pages == 14
    assert settings.crawl_time_budget_seconds == 8
    assert settings.retrieval_time_budget_seconds == 10
    assert provider_names == [
        "pubmed",
        "europe_pmc",
        "semantic_scholar",
        "official_health_api",
        "crawl4ai",
    ]


def test_evidence_policy_orders_trusted_guidelines_before_article_databases():
    ordered = sorted(
        [
            evidence_policy_sort_key(
                source="semantic_scholar",
                evidence_type="journal_article",
                url="https://www.semanticscholar.org/paper/example",
            ),
            evidence_policy_sort_key(
                source="pubmed",
                evidence_type="systematic_review",
                url="https://pubmed.ncbi.nlm.nih.gov/123/",
            ),
            evidence_policy_sort_key(
                source="crawl4ai",
                evidence_type="guideline",
                url="https://www.nice.org.uk/guidance/ng136",
            ),
            evidence_policy_sort_key(
                source="crawl4ai",
                evidence_type="guideline",
                url="https://www.afro.who.int/health-topics/malaria",
            ),
            evidence_policy_sort_key(
                source="crawl4ai",
                evidence_type="guideline",
                url="https://health.go.ug/downloads/malaria/",
            ),
        ]
    )

    assert ordered == [
        (0, 0),
        (1, 0),
        (1, 0),
        (3, 2),
        (4, 6),
    ]


def test_crawl_source_selection_uses_catalog_metadata_for_topic_relevance():
    settings = EvidenceRetrievalSettings(
        crawl_allowed_domains=[
            "who.int",
            "tbksp.who.int",
            "ncbi.nlm.nih.gov",
            "health.go.ug",
            "differentiatedservicedelivery.org",
            "iris.who.int",
            "idi.mak.ac.ug",
            "elearning.idi.co.ug",
            "unicef.org",
            "medicalguidelines.msf.org",
        ],
        crawl_max_sources=6,
    )
    provider = Crawl4AIProvider(settings)

    tb_sources = provider._select_sources("tuberculosis treatment regimen")
    nutrition_sources = provider._select_sources("severe malnutrition children treatment")

    assert not _catalog_source_is_uganda(tb_sources[0])
    assert _catalog_source_mentions(tb_sources[0], "tuberculosis", "tb")
    assert any(
        _catalog_source_mentions(source, "tuberculosis", "tb")
        for source in tb_sources[:3]
    )
    assert not any(
        _catalog_source_mentions(source, "hiv")
        and not _catalog_source_mentions(source, "tuberculosis", "tb")
        for source in tb_sources[:3]
    )
    assert _catalog_source_mentions(nutrition_sources[0], "malnutrition", "nutrition")
    assert any(
        not _catalog_source_is_uganda(source)
        and _catalog_source_mentions(source, "malnutrition", "nutrition")
        for source in nutrition_sources
    )


def test_crawl_catalog_contains_uganda_authority_source_hierarchy():
    settings = EvidenceRetrievalSettings()
    sources = load_crawl_sources(settings)
    source_text = "\n".join(_catalog_source_text(source) for source in sources)

    assert sources[0].name == "Uganda Ministry of Health Knowledge Management Portal"
    assert "library.health.go.ug" in source_text
    assert "nda.or.ug" in source_text
    assert "uniph.go.ug" in source_text
    assert "qadash.cphl.go.ug" in source_text
    assert "uci.or.ug" in source_text
    assert "ulii.org" in source_text
    assert "unicef uganda" in source_text


def test_crawl_source_selection_prioritizes_drug_monographs_for_dosage_queries():
    settings = EvidenceRetrievalSettings(
        crawl_allowed_domains=[
            "medicalguidelines.msf.org",
            "dailymed.nlm.nih.gov",
            "nih.gov",
            "who.int",
            "escardio.org",
        ],
        crawl_max_sources=6,
    )
    provider = Crawl4AIProvider(settings)

    sources = provider._select_sources(
        "ceftriaxone severe pneumonia adult drug monograph prescribing information dosage dose route frequency"
    )

    assert _catalog_source_mentions(sources[0], "drug", "dose", "dosage", "dosing", "route")
    assert sum(
        _catalog_source_mentions(source, "drug", "dose", "dosage", "dosing", "route")
        for source in sources[:3]
    ) >= 2
    assert not any(_catalog_source_mentions(source, "cardiology") for source in sources)


def test_crawl_source_selection_keeps_global_source_with_uganda_preferences():
    settings = EvidenceRetrievalSettings(
        crawl_allowed_domains=["health.go.ug", "library.health.go.ug", "who.int"],
        crawl_max_sources=2,
    )
    provider = Crawl4AIProvider(
        settings,
        sources=[
            CrawlSource(
                name="Uganda Ministry of Health",
                publisher="Ministry of Health Uganda",
                domains=("health.go.ug",),
                topics=("uganda", "malaria", "treatment", "guideline"),
                priority=1.0,
                seed_urls=("https://health.go.ug/downloads/malaria/",),
                search_urls=("https://health.go.ug/?s={query}",),
            ),
            CrawlSource(
                name="Uganda Clinical Guidelines",
                publisher="Ministry of Health Uganda",
                domains=("library.health.go.ug",),
                topics=("uganda", "clinical guidelines", "malaria", "treatment"),
                priority=0.99,
                seed_urls=("https://library.health.go.ug/example",),
                search_urls=("https://library.health.go.ug/?s={query}",),
            ),
            CrawlSource(
                name="World Health Organization",
                publisher="WHO",
                domains=("who.int",),
                topics=("who", "clinical guidelines", "malaria", "treatment"),
                priority=0.3,
                seed_urls=("https://www.who.int/teams/global-malaria-programme/guidelines-for-malaria",),
                search_urls=("https://www.who.int/search?query={query}",),
            ),
        ],
    )

    sources = [
        source.name
        for source in provider._select_sources("malaria treatment guideline in Uganda")
    ]

    assert len(sources) == 2
    assert any(source.startswith("Uganda") for source in sources)
    assert "World Health Organization" in sources


def test_quick_crawl_source_selection_keeps_malnutrition_specific_sources():
    settings = EvidenceRetrievalSettings(
        crawl_allowed_domains=[
            "platform.who.int",
            "who.int",
            "iris.who.int",
            "unicef.org",
            "reliefweb.int",
            "health.go.ug",
            "ncbi.nlm.nih.gov",
            "nih.gov",
        ],
        crawl_max_sources=4,
    )
    provider = Crawl4AIProvider(settings)

    sources = provider._select_sources(
        "treatment options severe malnutrition 5 child clinical guideline recommendation"
    )

    assert _catalog_source_mentions(sources[0], "malnutrition", "nutrition")
    assert any(
        not _catalog_source_is_uganda(source)
        and _catalog_source_mentions(source, "malnutrition", "nutrition")
        for source in sources
    )


def test_crawl_catalog_prioritizes_topical_sources_for_generic_clinical_queries():
    settings = EvidenceRetrievalSettings(crawl_max_sources=4)
    provider = Crawl4AIProvider(settings)
    catalog_sources = provider.sources

    queries = (
        (
            "What are the treatment options for severe malnutrition in children under 5?",
            ("malnutrition", "nutrition"),
        ),
        ("How is uncomplicated malaria treated in adults?", ("malaria",)),
        (
            "What is recommended first-line ART for adults with HIV?",
            ("hiv", "art", "antiretroviral"),
        ),
        (
            "What is the first-line antihypertensive medication for stage 1 hypertension?",
            ("hypertension", "cardiovascular"),
        ),
    )

    for query, topic_terms in queries:
        selected = provider._select_sources(query, catalog_sources)

        assert len(selected) == 4
        assert _catalog_source_mentions(selected[0], *topic_terms)
        assert any(not _catalog_source_is_uganda(source) for source in selected)


def test_crawl_catalog_honors_explicit_non_uganda_jurisdiction():
    settings = EvidenceRetrievalSettings(crawl_max_sources=4)
    provider = Crawl4AIProvider(settings)

    selected = provider._select_sources(
        "What is the first-line malaria treatment in Kenya?",
        provider.sources,
    )

    assert selected
    assert _catalog_source_mentions(selected[0], "kenya")
    assert not any(
        "ministry of health uganda" in _catalog_source_text(source)
        for source in selected[:2]
    )


@pytest.mark.integration
def test_live_crawl_retrieval_prioritizes_uganda_references(tmp_path):
    enabled = os.getenv("EMPIRICO_LIVE_EVIDENCE_TESTS", "").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        pytest.skip("set EMPIRICO_LIVE_EVIDENCE_TESTS=true to run live/cached crawl retrieval")

    catalog_sources = load_crawl_sources(EvidenceRetrievalSettings())
    settings = EvidenceRetrievalSettings(
        enable_crawl4ai=True,
        enable_crawl4ai_browser=False,
        crawl_allowed_domains=_catalog_domains(catalog_sources),
        crawl_cache_dir=os.getenv("CRAWL_CACHE_DIR") or str(tmp_path),
        crawl_max_sources=4,
        crawl_max_pages=8,
        crawl_time_budget_seconds=8,
        retrieval_time_budget_seconds=10,
        request_timeout_seconds=10,
        max_results_per_provider=4,
    )
    provider = Crawl4AIProvider(settings, sources=catalog_sources)

    items = provider.search(
        "What are the treatment options for severe malnutrition in children under 5?",
        max_results=4,
    )

    assert items
    first = items[0].model_dump(mode="json")
    first_text = " ".join(
        str(first.get(field) or "")
        for field in ("title", "journal_or_publisher", "url", "snippet")
    ).lower()
    assert "uganda" in first_text or "ministry of health uganda" in first_text
    assert len({item.url or item.full_text_url or item.id for item in items}) <= 4


def test_crawl_source_selection_includes_official_supplement_sources():
    settings = EvidenceRetrievalSettings(
        crawl_allowed_domains=["ods.od.nih.gov", "nih.gov", "who.int"],
        crawl_max_sources=4,
    )
    provider = Crawl4AIProvider(settings)

    sources = [
        source.name
        for source in provider._select_sources(
            "choline supplementation during pregnancy"
        )
    ]

    assert "NIH Office of Dietary Supplements" in sources


def test_crawl_source_selection_ignores_source_name_filler_terms():
    settings = EvidenceRetrievalSettings(crawl_max_sources=8)
    provider = Crawl4AIProvider(settings)
    query = "30 year old female in Kampala has HIV, what is the treatment for her?"
    eligible_sources = provider.sources

    terms = _source_selection_terms(query, eligible_sources)
    sources = [source.name for source in provider._select_sources(query, eligible_sources)]

    assert "for" not in terms
    assert "hiv" in terms
    assert "treatment" in terms
    assert any("HIV" in source for source in sources)


def test_crawl_content_focus_rejects_first_step_false_positive():
    query = "What is the first-line antihypertensive medication for stage 1 hypertension?"
    snippet = (
        "Estimates of the resources needed for recommended interventions have been added "
        "as a first step to guide the selection of intervention packages for malaria."
    )

    assert not _content_matches_core_query(
        query=query,
        title='Version updates to the "WHO guidelines for malaria"',
        url="https://cdn.who.int/media/docs/default-source/malaria/version-updates.pdf",
        snippet=snippet,
        focus_terms={"hypertension", "firstline"},
    )


def test_static_seed_targets_keep_first_url_from_each_selected_source(monkeypatch):
    settings = EvidenceRetrievalSettings(
        crawl_allowed_domains=["example.org"],
        crawl_max_pages=2,
        request_timeout_seconds=5,
    )
    provider = Crawl4AIProvider(
        settings,
        sources=[
            CrawlSource(
                name="Highly Matching Source",
                publisher="Example",
                domains=("example.org",),
                topics=("condition", "treatment", "regimen"),
                priority=1.0,
                seed_urls=(
                    "https://example.org/a1",
                    "https://example.org/a2",
                    "https://example.org/a3",
                ),
                search_urls=(),
            ),
            CrawlSource(
                name="Second Selected Source",
                publisher="Example",
                domains=("example.org",),
                topics=("condition",),
                priority=0.1,
                seed_urls=("https://example.org/b1",),
                search_urls=(),
            ),
        ],
    )
    captured_urls: list[str] = []

    def fake_fetch_static_targets(query, targets, timeout, settings, focus_terms, deadline=None):
        captured_urls.extend(target.url for target in targets)
        return []

    monkeypatch.setattr(crawl_provider_module, "_fetch_static_targets", fake_fetch_static_targets)

    provider._static_seed_items(
        "condition treatment regimen",
        provider.sources,
        max_results=1,
        deadline=time.perf_counter() + 10,
        focus_terms={"condition"},
    )

    assert len(captured_urls) == 2
    assert captured_urls[0].startswith("https://example.org/a")
    assert captured_urls[1] == "https://example.org/b1"


def test_query_plan_normalizes_without_medical_intent_dictionary():
    plan = build_query_plan(
        "What are the treatment options for severe malnutrition in children under 5?"
    )

    assert plan.intent_labels == ("semantic",)
    assert plan.population_terms == ()
    assert plan.section_terms == ()
    assert plan.evidence_terms == ()
    assert "malnutrition" in plan.content_terms
    assert "treatment" in plan.content_terms
    assert build_provider_query(
        "What are the treatment options for severe malnutrition in children under 5?",
        "crawl4ai",
    ) == "what are the treatment options for severe malnutrition in children under 5"


def test_query_plan_preserves_clinical_terms_without_dosage_expansion():
    question = "Calculate the dose for ceftriaxone for a 60kg adult with severe pneumonia"
    plan = build_query_plan(question)

    assert plan.intent_labels == ("semantic",)
    assert "ceftriaxone" in plan.content_terms
    assert "60kg" in plan.content_terms
    assert plan.evidence_terms == ()
    assert plan.section_terms == ()
    assert build_provider_query(question, "pubmed") == (
        "calculate the dose for ceftriaxone for a 60kg adult with severe pneumonia"
    )
    assert build_provider_query(question, "crawl4ai") == (
        "calculate the dose for ceftriaxone for a 60kg adult with severe pneumonia"
    )


def test_query_plan_does_not_infer_condition_specific_expansions():
    question = "30 year old female in Kampala has HIV, what is the treatment for her?"
    query = build_provider_query(question, "crawl4ai")

    assert "30" in query
    assert "old" in query
    assert "her" in query
    assert "hiv" in query
    assert "treatment" in query
    assert "kampala" in query
    assert "antiretroviral" not in query
    assert "art" not in query
    assert "regimen" not in query


def test_ranker_boosts_guideline_for_generic_treatment_question():
    guideline = EvidenceItem(
        id="guideline",
        source=EvidenceSource.CRAWL4AI,
        title="Clinical guideline for severe acute malnutrition",
        snippet="Recommendations for treatment and management.",
        journal_or_publisher="WHO",
        url="https://www.who.int/example",
        evidence_type="guideline",
    )
    article = EvidenceItem(
        id="article",
        source=EvidenceSource.SEMANTIC_SCHOLAR,
        title="Severe acute malnutrition treatment commentary",
        abstract="Treatment and management commentary.",
        journal_or_publisher="Journal",
        url="https://www.semanticscholar.org/paper/example",
        evidence_type="journal_article",
        citation_count=100,
    )

    ranked = rank_evidence_items("How should severe acute malnutrition be managed?", [article, guideline])

    assert ranked[0].id == "guideline"


def test_static_crawl_cache_round_trips_html(tmp_path):
    settings = EvidenceRetrievalSettings(
        crawl_cache_dir=str(tmp_path),
        crawl_cache_ttl_seconds=604800,
    )
    url = "https://www.who.int/example"

    _write_static_cache(
        settings,
        original_url=url,
        final_url=url,
        content_type="text/html",
        html="<html><title>WHO example</title><p>Guideline text</p></html>",
    )

    cached = _read_static_cache(settings, url)

    assert cached is not None
    assert cached["final_url"] == url
    assert "Guideline text" in str(cached["html"])


def test_pdf_seed_items_use_extracted_pdf_text_when_available(monkeypatch, tmp_path):
    settings = EvidenceRetrievalSettings(
        crawl_allowed_domains=["platform.who.int"],
        crawl_cache_dir=str(tmp_path),
        crawl_max_sources=1,
    )
    provider = Crawl4AIProvider(settings)
    source = CrawlSource(
        name="Uganda Integrated Management of Acute Malnutrition Guidelines",
        publisher="Ministry of Health Uganda",
        domains=("platform.who.int",),
        topics=(
            "uganda",
            "severe acute malnutrition",
            "children",
            "under five",
            "outpatient care",
            "inpatient care",
        ),
        priority=1.0,
        seed_urls=(
            "https://platform.who.int/docs/default-source/mca-documents/policy-documents/guideline/UGA-CH-38-03-GUIDELINE-2016-eng-IMAM-Guidelines-for-Uganda-Jan-2016.pdf",
        ),
        search_urls=(),
    )

    def fake_fetch_pdf_text(url, timeout, settings):
        return (
            url,
            (
                "Integrated management of acute malnutrition in children under five. "
                "Outpatient treatment for severe acute malnutrition includes ready-to-use "
                "therapeutic food, routine medicines, counselling, and follow-up. "
                "Complicated severe acute malnutrition requires inpatient stabilization "
                "with therapeutic milk and management of hypoglycaemia, hypothermia, "
                "dehydration, infection, and electrolyte imbalance."
            ),
            12,
        )

    monkeypatch.setattr(crawl_provider_module, "_fetch_pdf_text", fake_fetch_pdf_text)

    items = provider._pdf_seed_items(
        "What are the treatment options for severe malnutrition in children under 5?",
        [source],
        max_results=3,
        deadline=time.perf_counter() + 5,
    )

    assert len(items) == 1
    assert items[0].raw["retrieval_mode"] == "pdf_text"
    assert "ready-to-use therapeutic food" in str(items[0].snippet).lower()
    assert items[0].journal_or_publisher == "Ministry of Health Uganda"


def test_pdf_seed_items_keep_best_snippet_page_for_exact_reference_links(monkeypatch, tmp_path):
    settings = EvidenceRetrievalSettings(
        crawl_allowed_domains=["platform.who.int"],
        crawl_cache_dir=str(tmp_path),
        crawl_max_sources=1,
    )
    provider = Crawl4AIProvider(settings)
    source = CrawlSource(
        name="Uganda Integrated Management of Acute Malnutrition Guidelines",
        publisher="Ministry of Health Uganda",
        domains=("platform.who.int",),
        topics=("uganda", "severe acute malnutrition", "children", "treatment"),
        priority=1.0,
        seed_urls=("https://platform.who.int/docs/default-source/uganda-imam-guideline.pdf",),
        search_urls=(),
    )

    def fake_fetch_pdf_text(url, timeout, settings):
        return (
            url,
            (
                "Background and acknowledgements for the guideline.\n\n"
                "Outpatient therapeutic care treats children with severe acute malnutrition "
                "who have appetite and no medical complications with ready-to-use therapeutic "
                "food, routine medicines, counselling, and follow-up."
            ),
            80,
            [
                (5, "Background and acknowledgements for the guideline."),
                (
                    61,
                    "Outpatient therapeutic care treats children with severe acute malnutrition "
                    "who have appetite and no medical complications with ready-to-use therapeutic "
                    "food, routine medicines, counselling, and follow-up.",
                ),
            ],
        )

    monkeypatch.setattr(crawl_provider_module, "_fetch_pdf_text", fake_fetch_pdf_text)

    items = provider._pdf_seed_items(
        "What are the treatment options for severe malnutrition in children under 5?",
        [source],
        max_results=3,
        deadline=time.perf_counter() + 5,
    )
    citations = _citations_from_evidence([items[0].model_dump()])

    assert items[0].raw["page_start"] == 61
    assert str(citations[0]["url"]).endswith("#page=61")


def test_pdf_seed_items_fetch_candidates_in_parallel(monkeypatch, tmp_path):
    settings = EvidenceRetrievalSettings(
        crawl_allowed_domains=["example.org"],
        crawl_cache_dir=str(tmp_path),
        crawl_max_sources=3,
        crawl_time_budget_seconds=2,
        request_timeout_seconds=2,
    )
    provider = Crawl4AIProvider(
        settings,
        sources=[
            CrawlSource(
                name=f"Hypertension guideline {index}",
                publisher="Example Ministry",
                domains=("example.org",),
                topics=("hypertension", "treatment", "guideline"),
                priority=1.0,
                seed_urls=(f"https://example.org/hypertension-treatment-{index}.pdf",),
                search_urls=(),
            )
            for index in range(3)
        ],
    )
    lock = threading.Lock()
    active_fetches = 0
    max_active_fetches = 0

    def fake_fetch_pdf_text(url, timeout, settings):
        nonlocal active_fetches, max_active_fetches
        with lock:
            active_fetches += 1
            max_active_fetches = max(max_active_fetches, active_fetches)
        time.sleep(0.08)
        with lock:
            active_fetches -= 1
        return (
            url,
            "First-line hypertension treatment guidance names medicines and patient factors.",
            4,
            [(2, "First-line hypertension treatment guidance names medicines and patient factors.")],
        )

    monkeypatch.setattr(crawl_provider_module, "_fetch_pdf_text", fake_fetch_pdf_text)

    started_at = time.perf_counter()
    items = provider._pdf_seed_items(
        "hypertension treatment guideline",
        provider.sources,
        max_results=3,
        deadline=time.perf_counter() + 2,
        focus_terms={"hypertension", "treatment", "guideline"},
    )
    elapsed = time.perf_counter() - started_at

    assert len(items) == 3
    assert max_active_fetches >= 2
    assert elapsed < 0.18


def test_static_crawl_follows_trusted_download_link_to_pdf_text(monkeypatch, tmp_path):
    settings = EvidenceRetrievalSettings(
        crawl_allowed_domains=["who.int", "iris.who.int"],
        crawl_cache_dir=str(tmp_path),
        request_timeout_seconds=10,
    )
    page_url = "https://www.who.int/publications/i/item/9789240033986"
    document_url = "https://iris.who.int/server/api/core/bitstreams/example/content"
    html = f"""
    <html>
      <head><title>Guideline for the pharmacological treatment of hypertension in adults</title></head>
      <body>
        <a href={document_url} target="_blank">Download <span>(823.8 kB)</span></a>
        <p>Overview of pharmacological treatment for hypertension in adults.</p>
      </body>
    </html>
    """

    def fake_read_static_cache(settings, url):
        return {
            "final_url": page_url,
            "content_type": "text/html",
            "html": html,
        }

    def fake_fetch_pdf_text(url, timeout, settings):
        assert url == document_url
        return (
            url,
            (
                "Recommendation on initial treatment for adults with hypertension. "
                "For first-line antihypertensive medication, use a thiazide or "
                "thiazide-like diuretic, an ACE inhibitor or ARB, or a long-acting "
                "dihydropyridine calcium-channel blocker."
            ),
            48,
            [
                (30, "Background on hypertension diagnosis."),
                (
                    44,
                    "Recommendation on initial treatment for adults with hypertension. "
                    "For first-line antihypertensive medication, use a thiazide or "
                    "thiazide-like diuretic, an ACE inhibitor or ARB, or a long-acting "
                    "dihydropyridine calcium-channel blocker.",
                ),
            ],
        )

    monkeypatch.setattr(crawl_provider_module, "_read_static_cache", fake_read_static_cache)
    monkeypatch.setattr(crawl_provider_module, "_fetch_pdf_text", fake_fetch_pdf_text)

    item = crawl_provider_module._fetch_static_target(
        query="first line antihypertensive medication hypertension",
        target=crawl_provider_module.CrawlTarget(
            url=page_url,
            title_hint="WHO hypertension guideline",
            publisher="WHO",
            source_name="World Health Organization",
        ),
        timeout=5,
        settings=settings,
        focus_terms={"hypertension"},
    )

    assert item is not None
    assert item.raw["retrieval_mode"] == "linked_pdf_text"
    assert str(item.url) == document_url
    assert item.raw["page_start"] == 44
    assert "thiazide-like diuretic" in str(item.snippet)
    assert "ACE inhibitor or ARB" in str(item.snippet)


def test_pdf_text_cache_accepts_previous_schema_version(tmp_path):
    settings = EvidenceRetrievalSettings(crawl_cache_dir=str(tmp_path), crawl_cache_ttl_seconds=604800)
    document_url = "https://iris.who.int/server/api/core/bitstreams/example/content"
    cache_path = _pdf_text_cache_path(settings, document_url)
    assert cache_path is not None
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {
                "cache_version": 2,
                "fetched_at": time.time(),
                "original_url": document_url,
                "final_url": document_url,
                "pages_extracted": 58,
                "text": (
                    "For adults with hypertension requiring pharmacological treatment, "
                    "use drugs from any of the following three classes as initial treatment: "
                    "1. thiazide and thiazide-like agents 2. ACE inhibitors or ARBs "
                    "3. long-acting dihydropyridine calcium channel blockers."
                ),
                "page_texts": [
                    [
                        44,
                        (
                            "For adults with hypertension requiring pharmacological treatment, "
                            "use drugs from any of the following three classes as initial treatment."
                        ),
                    ]
                ],
            }
        ),
        encoding="utf-8",
    )

    cached = _read_pdf_text_cache(settings, document_url)

    assert cached is not None
    assert cached[0] == document_url
    assert cached[2] == 58
    assert cached[3][0][0] == 44
    assert "thiazide and thiazide-like agents" in cached[1]


def test_static_item_prefers_linked_pdf_recommendation_over_landing_page_summary():
    query = "What is the first-line antihypertensive medication for stage 1 hypertension?"
    html_item = EvidenceItem(
        id="crawl4ai:html",
        source=EvidenceSource.CRAWL4AI,
        title="Guideline for the pharmacological treatment of hypertension in adults",
        snippet=(
            "Hypertension can be defined using systolic and diastolic blood pressure levels. "
            "This guideline provides evidence-based public health guidance on the initiation "
            "of pharmacological agents for hypertension in adults."
        ),
        journal_or_publisher="WHO",
        url="https://www.who.int/publications/i/item/9789240033986",
        evidence_type="guideline",
        raw={"retrieval_mode": "static_html"},
    )
    linked_pdf_item = EvidenceItem(
        id="crawl4ai:pdf",
        source=EvidenceSource.CRAWL4AI,
        title="Guideline for the pharmacological treatment of hypertension in adults",
        snippet=(
            "Recommendation on initial treatment. For adults with hypertension requiring "
            "pharmacological treatment, use any of the following three classes as initial "
            "treatment: 1. thiazide and thiazide-like agents 2. ACE inhibitors or ARBs "
            "3. long-acting dihydropyridine calcium channel blockers."
        ),
        journal_or_publisher="WHO",
        url="https://iris.who.int/server/api/core/bitstreams/example/content",
        evidence_type="guideline",
        raw={"retrieval_mode": "linked_pdf_text", "generic_link_text": True},
    )

    selected = _best_static_item_for_query(query, html_item, linked_pdf_item)

    assert selected is linked_pdf_item


def test_static_crawl_keeps_html_when_pdf_link_is_lower_value(monkeypatch, tmp_path):
    settings = EvidenceRetrievalSettings(
        crawl_allowed_domains=["ncbi.nlm.nih.gov"],
        crawl_cache_dir=str(tmp_path),
        request_timeout_seconds=10,
    )
    page_url = "https://www.ncbi.nlm.nih.gov/books/NBK620318/"
    document_url = "https://www.ncbi.nlm.nih.gov/books/NBK620318/pdf/Bookshelf_NBK620318.pdf"
    html = f"""
    <html>
      <head><title>WHO updated recommendations on HIV clinical management</title></head>
      <body>
        <a href="{document_url}">PDF version of this title</a>
        <table>
          <tr>
            <td>
              Tenofovir disoproxil fumarate (TDF) or tenofovir alafenamide (TAF)
              plus lamivudine (3TC) or emtricitabine (FTC) is the preferred
              nucleoside reverse transcriptase inhibitor (NRTI) backbone for
              initial ART in adults and adolescents.
            </td>
          </tr>
        </table>
      </body>
    </html>
    """

    def fake_read_static_cache(settings, url):
        return {
            "final_url": page_url,
            "content_type": "text/html",
            "html": html,
        }

    def fake_fetch_pdf_text(url, timeout, settings):
        assert url == document_url
        return (
            url,
            (
                "References. Geneva: World Health Organization; 2024. "
                "Hill A, Perez A, Fairhead C. Systematic literature review on ART optimization."
            ),
            20,
        )

    monkeypatch.setattr(crawl_provider_module, "_read_static_cache", fake_read_static_cache)
    monkeypatch.setattr(crawl_provider_module, "_fetch_pdf_text", fake_fetch_pdf_text)

    item = crawl_provider_module._fetch_static_target(
        query="TDF 3TC DTG first-line ART adults HIV guideline NRTI backbone",
        target=crawl_provider_module.CrawlTarget(
            url=page_url,
            title_hint="WHO HIV updated recommendations",
            publisher="WHO / NCBI Bookshelf",
            source_name="WHO HIV Updated Recommendations - NCBI Bookshelf",
        ),
        timeout=5,
        settings=settings,
        focus_terms={"hiv", "art"},
    )

    assert item is not None
    assert item.raw["retrieval_mode"] == "static_html_cache"
    assert str(item.url) == page_url
    assert "preferred nucleoside reverse transcriptase inhibitor" in str(item.snippet)


def test_best_snippet_keeps_numbered_list_after_recommendation_colon():
    text = """
    4. RECOMMENDATION ON DRUG CLASSES TO BE USED AS FIRST-LINE AGENTS
    For adults with hypertension requiring pharmacological treatment, use any of the following classes as initial treatment:
    1. thiazide and thiazide-like agents
    2. angiotensin-converting enzyme inhibitors (ACEis)/angiotensin-receptor blockers (ARBs)
    3. long-acting dihydropyridine calcium channel blockers (CCBs).
    Strong recommendation, high-certainty evidence
    """

    snippet = _best_snippet(
        "first-line antihypertensive medication hypertension",
        text,
        max_chars=1200,
        max_segments=1,
    )

    assert "thiazide and thiazide-like agents" in snippet
    assert "angiotensin-converting enzyme inhibitors" in snippet
    assert "calcium channel blockers" in snippet


def test_first_line_guideline_snippet_keeps_step_one_treatment_window():
    markdown = "\n".join(
        [
            "Hypertension in adults: diagnosis and management",
            (
                "Discuss starting antihypertensive drug treatment with adults under 80 "
                "with persistent stage 1 hypertension and target organ damage."
            ),
            "Lifestyle advice should be offered to adults with raised blood pressure.",
            "Monitoring recommendations cover clinic and ambulatory blood pressure.",
            (
                "Step 1 treatment: offer an ACE inhibitor or an angiotensin receptor "
                "blocker to adults starting step 1 antihypertensive treatment when "
                "clinically appropriate."
            ),
            (
                "Offer a calcium-channel blocker as step 1 antihypertensive treatment "
                "for adults aged 55 or over or adults of Black African or African-Caribbean "
                "family origin."
            ),
        ]
    )

    snippet = _best_snippet(
        "What is the first-line antihypertensive medication for stage 1 hypertension?",
        markdown,
    )

    assert "persistent stage 1 hypertension" in snippet
    assert "Step 1 treatment" in snippet
    assert "ACE inhibitor" in snippet


def test_guideline_snippet_prefers_body_text_over_pdf_contents_noise():
    markdown = "\n\n".join(
        [
            (
                "TABLE OF CONTENTS Chapter five outpatient therapeutic care for severe "
                "acute malnutrition ..... 59 Chapter six inpatient therapeutic care "
                "for severe acute malnutrition ..... 73"
            ),
            (
                "Outpatient therapeutic care treats children with severe acute malnutrition "
                "who have appetite and no medical complications with ready-to-use therapeutic "
                "food, routine medicines, counselling, and weekly follow-up."
            ),
            (
                "Inpatient therapeutic care is used when severe acute malnutrition is "
                "complicated by danger signs or medical complications, with stabilization, "
                "therapeutic feeds, antibiotics when indicated, and careful monitoring."
            ),
        ]
    )

    snippet = _best_snippet(
        "What are the treatment options for severe malnutrition in children under 5?",
        markdown,
    )

    assert "ready-to-use therapeutic food" in snippet
    assert "TABLE OF CONTENTS" not in snippet


def test_guideline_snippet_prefers_recommendations_over_bibliography_noise():
    markdown = "\n\n".join(
        [
            (
                "34. La Rosa AM, Harrison LJ, Taiwo B et al; ACTG Study Group. "
                "Raltegravir in second-line antiretroviral therapy. Lancet HIV. "
                "2016;3(6):e247-e258. doi: 10.1016/S2352-3018(16)30002-X."
            ),
            (
                "Preferred first-line antiretroviral therapy regimens for adults "
                "and adolescents living with HIV should use a dolutegravir-containing "
                "regimen when clinically appropriate."
            ),
        ]
    )

    snippet = _best_snippet(
        "first-line antiretroviral therapy HIV regimen adults",
        markdown,
    )

    assert "dolutegravir-containing regimen" in snippet
    assert "doi:" not in snippet


def test_guideline_snippet_prefers_recommendations_over_acknowledgements_noise():
    markdown = "\n\n".join(
        [
            (
                "WHO gratefully acknowledges the members of the Guideline Development "
                "Group from Kampala, Uganda, Geneva, and Sydney."
            ),
            (
                "Preferred antiretroviral therapy for adults living with HIV should "
                "use a dolutegravir-containing regimen when clinically appropriate."
            ),
        ]
    )

    snippet = _best_snippet(
        "HIV treatment guidelines Kampala Uganda adult",
        markdown,
    )

    assert "dolutegravir-containing regimen" in snippet
    assert "acknowledges" not in snippet


def test_evidence_country_hint_defaults_to_uganda(monkeypatch):
    monkeypatch.delenv("EMPIRICO_EVIDENCE_COUNTRY_CODE", raising=False)
    monkeypatch.delenv("EMPIRICO_MODEL_SERVICE_COUNTRY_CODE", raising=False)

    assert _evidence_country_code_for_search() == "UG"


def test_evidence_country_hint_can_be_global(monkeypatch):
    monkeypatch.setenv("EMPIRICO_EVIDENCE_COUNTRY_CODE", "global")

    assert _evidence_country_code_for_search() == "GLOBAL"


def test_legacy_country_hint_is_still_honored(monkeypatch):
    monkeypatch.delenv("EMPIRICO_EVIDENCE_COUNTRY_CODE", raising=False)
    monkeypatch.setenv("EMPIRICO_MODEL_SERVICE_COUNTRY_CODE", "ug")

    assert _evidence_country_code_for_search() == "UG"


def test_explicit_retrieval_query_country_overrides_uganda_default():
    assert _country_code_for_retrieval_query("UG", "malaria treatment in Kenya") == "KE"
    assert _country_code_for_retrieval_query("UG", "malaria treatment in Tanzania") == "TZ"
    assert _country_code_for_retrieval_query("UG", "malaria treatment in Uganda") == "UG"
    assert _country_code_for_retrieval_query("GLOBAL", "malaria treatment in Uganda") == "GLOBAL"


def test_local_evidence_provider_mode_defaults_by_search_depth(monkeypatch):
    monkeypatch.delenv("EMPIRICO_EVIDENCE_PROVIDER_MODE", raising=False)
    monkeypatch.delenv("EMPIRICO_QUICK_EVIDENCE_PROVIDER_MODE", raising=False)
    monkeypatch.delenv("EMPIRICO_DEEP_EVIDENCE_PROVIDER_MODE", raising=False)

    assert _local_evidence_provider_mode(False) == "crawl"
    assert _local_evidence_provider_mode(True) == "web"


def test_local_evidence_provider_mode_honors_crawl_alias(monkeypatch):
    monkeypatch.setenv("EMPIRICO_EVIDENCE_PROVIDER_MODE", "crawl")

    assert _local_evidence_provider_mode(False) == "crawl"
    assert _local_evidence_provider_mode(True) == "crawl"


def test_source_preference_terms_are_configurable(monkeypatch):
    monkeypatch.setenv("EMPIRICO_SOURCE_PREFERENCE_TERMS", "health.go.ug; WHO AFRO\nAfrica")

    assert _source_preference_terms() == ("health.go.ug", "who afro", "africa")


def test_default_source_preference_terms_are_uganda_first(monkeypatch):
    monkeypatch.delenv("EMPIRICO_SOURCE_PREFERENCE_TERMS", raising=False)

    terms = _source_preference_terms()

    assert "uganda" in terms
    assert "library.health.go.ug" in terms
    assert "nda.or.ug" in terms


def test_source_preferences_apply_by_default_unless_another_jurisdiction_is_explicit():
    terms = ("uganda", "health.go.ug", "who afro", "africa")

    assert _active_source_preference_terms(
        "first-line treatment for stage 1 hypertension",
        terms,
    ) == terms
    assert _active_source_preference_terms(
        "HIV treatment guideline Uganda",
        terms,
    ) == terms
    assert _active_source_preference_terms(
        "HIV treatment guideline Kenya",
        terms,
    ) == ()


def test_generic_query_uses_configured_local_source_preference(monkeypatch):
    monkeypatch.setenv("EMPIRICO_QUICK_ENABLE_RETRIEVAL_PLANNER", "false")
    monkeypatch.setenv(
        "EMPIRICO_SOURCE_PREFERENCE_TERMS",
        "uganda,health.go.ug,ministry of health uganda,who afro,africa",
    )
    question = "What is the first-line antihypertensive medication for stage 1 hypertension?"
    configured_terms = _source_preference_terms()

    assert _active_source_preference_terms(question, configured_terms) == configured_terms

    queries = asyncio.run(
        _retrieval_queries_for_request(
            query=question,
            patient_data="",
            chat_history="",
            deep_search=False,
        )
    )

    assert queries == (question,)


def test_direct_retrieval_preserves_explicit_other_jurisdiction(monkeypatch):
    monkeypatch.setenv("EMPIRICO_QUICK_ENABLE_RETRIEVAL_PLANNER", "false")
    question = "What is the first-line malaria treatment in Kenya?"

    queries = asyncio.run(
        _retrieval_queries_for_request(
            query=question,
            patient_data="",
            chat_history="",
            deep_search=False,
        )
    )

    assert queries == (question,)


def test_quick_defaults_use_uganda_crawl_and_planner(monkeypatch):
    for key in (
        "EMPIRICO_EVIDENCE_PROVIDER_MODE",
        "EMPIRICO_QUICK_EVIDENCE_PROVIDER_MODE",
        "EMPIRICO_ENABLE_RETRIEVAL_PLANNER",
        "EMPIRICO_QUICK_ENABLE_RETRIEVAL_PLANNER",
    ):
        monkeypatch.delenv(key, raising=False)

    assert _local_evidence_provider_mode(False) == "crawl"
    assert _retrieval_planner_enabled(False) is True
    assert _evidence_country_code_for_search() == "UG"


def test_quick_retrieval_stops_after_direct_query_when_sources_are_ready(monkeypatch):
    calls: list[str] = []
    first_query = "hypertension treatment"
    second_query = "Uganda clinical guidelines Ministry of Health Uganda hypertension treatment"

    async def fake_search_local_evidence(**kwargs):
        calls.append(kwargs["query"])
        if kwargs["query"] != first_query:
            raise AssertionError("the fallback query should not run when four sources are ready")
        return {
            "items": [
                {
                    "source": "crawl4ai",
                    "title": f"Hypertension treatment source {index}",
                    "url": f"https://example.org/hypertension-treatment-{index}",
                    "journal_or_publisher": "Guideline",
                    "year": 2026 - index,
                    "snippet": "Hypertension treatment guidance includes first-line medicines and patient factors.",
                    "evidence_type": "guideline",
                    "raw": {"retrieval_mode": "static_html"},
                }
                for index in range(1, 5)
            ],
            "provider_errors": [],
            "timings_ms": {"total": 100.0},
        }

    monkeypatch.setenv("EMPIRICO_QUICK_RETRIEVAL_EARLY_STOP", "true")
    monkeypatch.setattr(
        "healthnavi.services.evidence_retrieval_adapter._search_local_evidence",
        fake_search_local_evidence,
    )

    result = asyncio.run(
        _search_retrieval_queries(
            queries=(first_query, second_query),
            top_k=8,
            country_code=None,
            deep_search=False,
            source_preference_terms=(),
            answer_top_k=4,
        )
    )

    assert calls == [first_query]
    assert len(result["items"]) == 4
    assert result["timings_ms"]["early_stop"] is True
    assert "query_2" not in result["timings_ms"]


def test_quick_retrieval_runs_fallback_query_when_first_query_is_insufficient(monkeypatch):
    calls: list[str] = []
    first_query = "hypertension treatment"
    second_query = "Uganda clinical guidelines Ministry of Health Uganda hypertension treatment"

    async def fake_search_local_evidence(**kwargs):
        calls.append(kwargs["query"])
        item_count = 2 if kwargs["query"] == first_query else 3
        return {
            "items": [
                {
                    "source": "crawl4ai",
                    "title": f"{kwargs['query']} source {index}",
                    "url": f"https://example.org/{len(calls)}-{index}",
                    "journal_or_publisher": "Guideline",
                    "year": 2026 - index,
                    "snippet": "Hypertension treatment guidance includes first-line medicines and patient factors.",
                    "evidence_type": "guideline",
                    "raw": {"retrieval_mode": "static_html"},
                }
                for index in range(1, item_count + 1)
            ],
            "provider_errors": [],
            "timings_ms": {"total": 100.0},
        }

    monkeypatch.setenv("EMPIRICO_QUICK_RETRIEVAL_EARLY_STOP", "true")
    monkeypatch.setattr(
        "healthnavi.services.evidence_retrieval_adapter._search_local_evidence",
        fake_search_local_evidence,
    )

    result = asyncio.run(
        _search_retrieval_queries(
            queries=(first_query, second_query),
            top_k=8,
            country_code=None,
            deep_search=False,
            source_preference_terms=(),
            answer_top_k=4,
        )
    )

    assert calls == [first_query, second_query]
    assert len(result["items"]) == 5
    assert "early_stop" not in result["timings_ms"]
    assert "query_2" in result["timings_ms"]


def test_duplicate_document_retrieval_preserves_distinct_passages():
    generic_item = {
        "id": "crawl4ai:https://example.org/hypertension-guideline.pdf",
        "title": "Hypertension guideline",
        "url": "https://example.org/hypertension-guideline.pdf",
        "final_score": 0.7205,
        "relevance_score": 0.212,
        "snippet": (
            "Hypertension can be defined using specific blood pressure levels. "
            "The guideline provides public health guidance on hypertension care."
        ),
        "raw": {"query_used": "Uganda clinical guidelines hypertension"},
    }
    recommendation_item = {
        **generic_item,
        "final_score": 0.7314,
        "relevance_score": 0.2404,
        "snippet": (
            "Recommendation on drug classes to be used as first-line agents: "
            "thiazide and thiazide-like agents; ACE inhibitors or ARBs; "
            "long-acting dihydropyridine calcium channel blockers."
        ),
        "raw": {"query_used": "first-line antihypertensive medication"},
    }

    merged = _merge_evidence_items([generic_item], [recommendation_item])

    assert len(merged) == 2
    assert [item["raw"]["query_used"] for item in merged] == [
        "Uganda clinical guidelines hypertension",
        "first-line antihypertensive medication",
    ]
    assert "thiazide and thiazide-like agents" in merged[1]["snippet"]
    assert len(_unique_evidence_passages(merged, limit=4)) == 2


def test_exact_duplicate_passages_keep_higher_scored_item():
    weaker_item = {
        "id": "crawl4ai:https://example.org/hypertension-guideline.pdf",
        "title": "Hypertension guideline",
        "url": "https://example.org/hypertension-guideline.pdf",
        "final_score": 0.5,
        "relevance_score": 0.2,
        "snippet": "Initial hypertension treatment includes several first-line medicine classes.",
    }
    stronger_item = {
        **weaker_item,
        "final_score": 0.8,
        "raw": {"query_used": "first-line hypertension medicines"},
    }

    merged = _merge_evidence_items([weaker_item], [stronger_item])

    assert len(merged) == 1
    assert merged[0]["final_score"] == 0.8
    assert merged[0]["raw"]["query_used"] == "first-line hypertension medicines"


def test_ranker_deduplicate_items_preserves_distinct_document_passages():
    shared = {
        "id": "crawl4ai:https://example.org/guideline.pdf",
        "source": "crawl4ai",
        "title": "Clinical guideline",
        "url": "https://example.org/guideline.pdf",
        "evidence_type": "guideline",
    }
    items = [
        EvidenceItem(
            **shared,
            snippet="Diagnostic criteria are described in this passage.",
            raw={"page_start": 10, "section_title": "Diagnosis"},
        ),
        EvidenceItem(
            **shared,
            snippet="Treatment options are described in this different passage.",
            raw={"page_start": 22, "section_title": "Treatment"},
        ),
        EvidenceItem(
            **shared,
            snippet="Treatment options are described in this different passage.",
            raw={"page_start": 22, "section_title": "Treatment"},
        ),
    ]

    deduped = deduplicate_items(items)

    assert len(deduped) == 2
    assert [item.raw["section_title"] for item in deduped] == ["Diagnosis", "Treatment"]


def test_quick_retrieval_hedges_when_direct_query_is_slow(monkeypatch):
    calls: list[str] = []
    first_query = "hypertension treatment"
    second_query = "Uganda clinical guidelines Ministry of Health Uganda hypertension treatment"

    async def fake_search_local_evidence(**kwargs):
        calls.append(kwargs["query"])
        if kwargs["query"] == first_query:
            await asyncio.sleep(0.15)
        return {
            "items": [
                {
                    "source": "crawl4ai",
                    "title": f"{kwargs['query']} source {index}",
                    "url": f"https://example.org/{kwargs['query'].replace(' ', '-')}-{index}",
                    "journal_or_publisher": "Guideline",
                    "year": 2026 - index,
                    "snippet": "Hypertension treatment guidance includes first-line medicines and patient factors.",
                    "evidence_type": "guideline",
                    "raw": {"retrieval_mode": "static_html"},
                }
                for index in range(1, 5)
            ],
            "provider_errors": [],
            "timings_ms": {"total": 100.0},
        }

    monkeypatch.setenv("EMPIRICO_QUICK_RETRIEVAL_EARLY_STOP", "true")
    monkeypatch.setenv("EMPIRICO_QUICK_RETRIEVAL_EARLY_STOP_WAIT_SECONDS", "0.01")
    monkeypatch.setattr(
        "healthnavi.services.evidence_retrieval_adapter._search_local_evidence",
        fake_search_local_evidence,
    )

    result = asyncio.run(
        _search_retrieval_queries(
            queries=(first_query, second_query),
            top_k=8,
            country_code=None,
            deep_search=False,
            source_preference_terms=(),
            answer_top_k=4,
        )
    )

    assert calls == [first_query, second_query]
    assert len(result["items"]) == 8
    assert "early_stop" not in result["timings_ms"]
    assert "query_1" in result["timings_ms"]
    assert "query_2" in result["timings_ms"]


def test_quick_rescue_uses_remaining_latency_budget(monkeypatch):
    captured_calls: list[dict] = []

    async def fake_search_retrieval_queries(**kwargs):
        captured_calls.append(kwargs)
        return {"items": [], "provider_errors": [], "timings_ms": {}}

    monkeypatch.setenv("EMPIRICO_ENABLE_EVIDENCE_RESCUE", "true")
    monkeypatch.setenv("EMPIRICO_QUICK_EVIDENCE_PROVIDER_MODE", "crawl")
    monkeypatch.setenv("EMPIRICO_QUICK_RESCUE_MIN_SECONDS", "1")
    monkeypatch.setattr(
        "healthnavi.services.evidence_retrieval_adapter._search_retrieval_queries",
        fake_search_retrieval_queries,
    )

    result = asyncio.run(
        _rescue_evidence_search(
            queries=("hypertension treatment",),
            top_k=8,
            country_code=None,
            deep_search=False,
            answer_top_k=4,
            latency_deadline=time.perf_counter() + 5,
        )
    )

    assert result["items"] == []
    assert len(captured_calls) == 1
    assert captured_calls[0]["provider_mode"] == "web"
    rescue_settings = captured_calls[0]["search_settings"]
    assert rescue_settings.retrieval_time_budget_seconds < 5
    assert rescue_settings.retrieval_time_budget_seconds <= 4.5
    assert rescue_settings.crawl_time_budget_seconds <= rescue_settings.retrieval_time_budget_seconds


def test_quick_rescue_skips_when_latency_budget_is_spent(monkeypatch):
    async def fail_search_retrieval_queries(**kwargs):
        raise AssertionError("rescue search should not run after the quick budget is spent")

    monkeypatch.setenv("EMPIRICO_ENABLE_EVIDENCE_RESCUE", "true")
    monkeypatch.setenv("EMPIRICO_QUICK_EVIDENCE_PROVIDER_MODE", "crawl")
    monkeypatch.setattr(
        "healthnavi.services.evidence_retrieval_adapter._search_retrieval_queries",
        fail_search_retrieval_queries,
    )

    result = asyncio.run(
        _rescue_evidence_search(
            queries=("hypertension treatment",),
            top_k=8,
            country_code=None,
            deep_search=False,
            answer_top_k=4,
            latency_deadline=time.perf_counter() + 0.5,
        )
    )

    assert result == {
        "items": [],
        "provider_errors": [],
        "timings_ms": {"skipped": "latency_budget"},
    }


def test_retrieval_query_planner_uses_model_json(monkeypatch):
    async def fake_post_model_response(payload, timeout_seconds):
        assert payload["prompt_type"] == "empirico_retrieval_query_plan"
        assert "Return only valid JSON" in payload["prompt"]
        return {
            "answer": (
                '{"queries":["adult HIV treatment Kampala",'
                '"HIV antiretroviral therapy guideline Uganda"]}'
            )
        }

    monkeypatch.setattr(
        "healthnavi.services.evidence_retrieval_adapter._post_model_response",
        fake_post_model_response,
    )
    monkeypatch.setenv("EMPIRICO_DEEP_ENABLE_RETRIEVAL_PLANNER", "true")

    queries = asyncio.run(
        _retrieval_queries_for_request(
            query="30 year old female in Kampala has HIV, what is the treatment for her?",
            patient_data="",
            chat_history="",
            deep_search=True,
        )
    )

    assert queries == (
        "30 year old female in Kampala has HIV, what is the treatment for her?",
        "adult HIV treatment Kampala",
        "HIV antiretroviral therapy guideline Uganda",
    )


def test_evidence_request_planner_returns_question_plan_and_queries(monkeypatch):
    async def fake_post_model_response(payload, timeout_seconds):
        assert payload["prompt_type"] == "empirico_retrieval_query_plan"
        assert "clinical_question" in payload["prompt"]
        assert "answer_requirements" in payload["prompt"]
        assert "Infer the clinical task semantically" in payload["prompt"]
        return {
            "answer": json.dumps(
                {
                    "clinical_question": "What does low TSH with high free T4 mean?",
                    "task": "laboratory interpretation",
                    "population": "",
                    "condition": "low TSH with high free T4",
                    "requested_output": "interpretation and next steps",
                    "answer_requirements": [
                        "most likely interpretation",
                        "important differential explanations",
                        "relevant next investigations",
                    ],
                    "evidence_goals": [
                        "thyroid function test interpretation",
                        "confirmatory investigation guidance",
                    ],
                    "queries": [
                        "low TSH high free T4 interpretation",
                        "thyroid function test interpretation guideline",
                    ],
                }
            )
        }

    monkeypatch.setenv("EMPIRICO_QUICK_ENABLE_RETRIEVAL_PLANNER", "true")
    monkeypatch.setattr(
        "healthnavi.services.evidence_retrieval_adapter._post_model_response",
        fake_post_model_response,
    )

    plan, queries = asyncio.run(
        _evidence_request_plan_for_request(
            query="What does low TSH with high free T4 mean?",
            patient_data="",
            chat_history="",
            deep_search=False,
        )
    )

    assert plan["task"] == "laboratory interpretation"
    assert "most likely interpretation" in plan["answer_requirements"]
    assert queries == (
        "What does low TSH with high free T4 mean?",
        "low TSH high free T4 interpretation",
        "thyroid function test interpretation guideline",
    )


def test_quick_response_uses_direct_retrieval_and_relevant_source_contract(monkeypatch):
    retrieval_calls = []

    async def fake_search_retrieval_queries(**kwargs):
        retrieval_calls.append(kwargs)
        return {
            "items": [
                {
                    "source": "crawl4ai",
                    "title": "Guideline for pharmacological treatment of hypertension in adults",
                    "url": "https://iris.who.int/example",
                    "journal_or_publisher": "WHO",
                    "year": 2021,
                    "snippet": "Initial treatment can include thiazide-like agents, ACE inhibitors or ARBs, or long-acting dihydropyridine calcium channel blockers.",
                    "evidence_type": "guideline",
                }
            ],
            "provider_errors": [],
            "timings_ms": {"total": 100.0},
        }

    async def fake_post_model_response(payload, timeout_seconds):
        assert payload["prompt_type"] == "empirico_quick_search"
        assert payload["model"] == "gemini-2.5-flash-lite"
        assert payload["max_output_tokens"] == 2000
        assert payload["temperature"] == 0.2
        assert payload["prompt"].startswith("You are Empirico")
        assert "This deployment serves clinicians in Uganda" in payload["prompt"]
        assert "This is a quick answer" in payload["prompt"]
        assert (
            "## QUESTION\nWhat is the first-line antihypertensive medication for stage 1 hypertension?"
            in payload["prompt"]
        )
        assert (
            "[1] Guideline for pharmacological treatment of hypertension in adults (WHO, 2021)"
            in payload["prompt"]
        )
        assert "Excerpt: Initial treatment can include thiazide-like agents" in payload["prompt"]
        return {
            "answer": (
                "There is no single universal first-line antihypertensive for every adult with stage 1 hypertension; "
                "when medication is indicated, use a thiazide or thiazide-like diuretic, an ACE inhibitor or ARB, "
                "or a long-acting dihydropyridine calcium-channel blocker [1].\n\n"
                "In practice, common examples include hydrochlorothiazide or chlorthalidone/indapamide for the "
                "thiazide group, enalapril or lisinopril for ACE inhibitors, losartan for an ARB, and amlodipine "
                "or long-acting nifedipine for a dihydropyridine CCB. Choose between them using age, pregnancy "
                "status, kidney disease, diabetes, drug interactions, adverse-effect risk, baseline potassium or "
                "creatinine concerns, and local availability [1]."
            ),
            "diagnosis_complete": True,
        }

    monkeypatch.setenv("EMPIRICO_FOLLOWUP_MODE", "off")
    monkeypatch.setenv("EMPIRICO_QUICK_MODEL_NAME", "gemini-2.5-flash-lite")
    monkeypatch.delenv("EMPIRICO_QUICK_MAX_OUTPUT_TOKENS", raising=False)
    monkeypatch.setenv("EMPIRICO_QUICK_SEARCH_TOP_K", "8")
    monkeypatch.setenv("EMPIRICO_QUICK_ENABLE_RETRIEVAL_PLANNER", "false")
    monkeypatch.setattr(
        "healthnavi.services.evidence_retrieval_adapter._search_retrieval_queries",
        fake_search_retrieval_queries,
    )
    monkeypatch.setattr(
        "healthnavi.services.evidence_retrieval_adapter._post_model_response",
        fake_post_model_response,
    )

    answer, complete, prompt_type, followups = asyncio.run(
        generate_model_service_response(
            query="What is the first-line antihypertensive medication for stage 1 hypertension?",
            chat_history="",
            patient_data="",
            deep_search=False,
        )
    )

    assert len(retrieval_calls) == 1
    assert retrieval_calls[0]["queries"] == (
        "What is the first-line antihypertensive medication for stage 1 hypertension?",
    )
    assert "uganda" in retrieval_calls[0]["source_preference_terms"]
    assert "library.health.go.ug" in retrieval_calls[0]["source_preference_terms"]
    assert retrieval_calls[0]["top_k"] == 8
    assert retrieval_calls[0]["deep_search"] is False
    assert _answer_top_k(False) == 4
    assert "[1](https://iris.who.int/example" in answer
    assert complete is True
    assert prompt_type == "empirico_quick_search"
    assert followups == []


def test_quick_answer_call_is_not_starved_by_latency_target(monkeypatch):
    model_timeouts: list[float] = []

    async def fake_search_retrieval_queries(**kwargs):
        return {
            "items": [
                {
                    "source": "crawl4ai",
                    "title": "Uganda cough guideline",
                    "url": "https://health.go.ug/cough",
                    "journal_or_publisher": "Ministry of Health Uganda",
                    "year": 2025,
                    "snippet": "Cough assessment considers duration, fever, breathing difficulty, and danger signs.",
                    "evidence_type": "guideline",
                    "raw": {"retrieval_mode": "static_html"},
                }
            ],
            "provider_errors": [],
            "timings_ms": {"total": 100.0},
        }

    async def fake_post_model_response(payload, timeout_seconds):
        model_timeouts.append(timeout_seconds)
        return {
            "answer": (
                "Assess cough by duration and danger signs such as fever or difficulty breathing [1]."
            ),
            "diagnosis_complete": True,
        }

    monkeypatch.setenv("EMPIRICO_FOLLOWUP_MODE", "off")
    monkeypatch.setenv("EMPIRICO_QUICK_ENABLE_RETRIEVAL_PLANNER", "false")
    monkeypatch.setenv("EMPIRICO_QUICK_LATENCY_TARGET_SECONDS", "5")
    monkeypatch.setenv("EMPIRICO_QUICK_MODEL_TIMEOUT_SECONDS", "45")
    monkeypatch.setattr(
        "healthnavi.services.evidence_retrieval_adapter._search_retrieval_queries",
        fake_search_retrieval_queries,
    )
    monkeypatch.setattr(
        "healthnavi.services.evidence_retrieval_adapter._post_model_response",
        fake_post_model_response,
    )

    answer, complete, prompt_type, followups = asyncio.run(
        generate_model_service_response(
            query="What danger signs matter with cough?",
            chat_history="",
            patient_data="",
            deep_search=False,
        )
    )

    # The quick latency target bounds retrieval, never the answer call itself.
    assert model_timeouts == [45.0]
    assert "[1](https://health.go.ug/cough" in answer
    assert complete is True
    assert prompt_type == "empirico_quick_search"
    assert followups == []


def test_quick_response_deduplicates_and_compacts_references(monkeypatch):
    async def fake_search_retrieval_queries(**kwargs):
        return {
            "items": [
                {
                    "source": "crawl4ai",
                    "title": "Uganda hypertension guideline",
                    "url": "https://health.go.ug/hypertension",
                    "journal_or_publisher": "Ministry of Health Uganda",
                    "year": 2023,
                    "snippet": "Hypertension treatment guidance for adults.",
                    "evidence_type": "guideline",
                    "raw": {"retrieval_mode": "static_html"},
                },
                {
                    "source": "crawl4ai",
                    "title": "Uganda hypertension guideline",
                    "url": "https://health.go.ug/hypertension",
                    "journal_or_publisher": "Ministry of Health Uganda",
                    "year": 2023,
                    "snippet": "Duplicate passage restating hypertension treatment guidance for adults.",
                    "evidence_type": "guideline",
                    "raw": {"retrieval_mode": "static_html"},
                },
                {
                    "source": "crawl4ai",
                    "title": "WHO hypertension guideline",
                    "url": "https://www.who.int/hypertension-guideline",
                    "journal_or_publisher": "WHO",
                    "year": 2025,
                    "snippet": "Current hypertension guideline recommendations.",
                    "evidence_type": "guideline",
                    "raw": {"retrieval_mode": "static_html"},
                },
                {
                    "source": "pubmed",
                    "title": "Hypertension treatment review",
                    "url": "https://pubmed.ncbi.nlm.nih.gov/123/",
                    "journal_or_publisher": "Lancet",
                    "year": 2024,
                    "abstract": "Review of hypertension treatment choices.",
                    "evidence_type": "review",
                },
                {
                    "source": "europe_pmc",
                    "title": "Hypertension medication evidence",
                    "url": "https://europepmc.org/article/MED/456",
                    "journal_or_publisher": "NEJM",
                    "year": 2024,
                    "abstract": "Evidence on hypertension medication selection.",
                    "evidence_type": "journal_article",
                },
            ],
            "provider_errors": [],
            "timings_ms": {"total": 100.0},
        }

    async def fake_post_model_response(payload, timeout_seconds):
        assert payload["prompt_type"] == "empirico_quick_search"
        # Uganda guideline first, then WHO, then article-database results. The two
        # passages from the same Uganda page are offered as one source with both excerpts.
        assert "[1] Uganda hypertension guideline (Ministry of Health Uganda, 2023)" in payload["prompt"]
        assert (
            "Hypertension treatment guidance for adults. [...] Duplicate passage restating "
            "hypertension treatment guidance for adults." in payload["prompt"]
        )
        assert "[2] WHO hypertension guideline (WHO, 2025)" in payload["prompt"]
        assert "[3] Hypertension treatment review (Lancet, 2024)" in payload["prompt"]
        assert "[4] Hypertension medication evidence (NEJM, 2024)" in payload["prompt"]
        assert "[5]" not in payload["prompt"]
        return {
            "answer": (
                "Use guideline-supported first-line antihypertensive options when medication is indicated [2][1].\n\n"
                "Supporting review evidence can help when options are otherwise similar [3]."
            ),
            "diagnosis_complete": True,
        }

    monkeypatch.setenv("EMPIRICO_FOLLOWUP_MODE", "off")
    monkeypatch.setenv("EMPIRICO_QUICK_ENABLE_RETRIEVAL_PLANNER", "false")
    monkeypatch.setattr(
        "healthnavi.services.evidence_retrieval_adapter._search_retrieval_queries",
        fake_search_retrieval_queries,
    )
    monkeypatch.setattr(
        "healthnavi.services.evidence_retrieval_adapter._post_model_response",
        fake_post_model_response,
    )

    answer, _, _, _ = asyncio.run(
        generate_model_service_response(
            query="What is first-line treatment for hypertension?",
            chat_history="",
            patient_data="",
            deep_search=False,
        )
    )

    # The model cited WHO first, so display numbering follows first use in the answer,
    # and only cited sources appear in References.
    assert "1. [WHO hypertension guideline]" in answer
    assert "2. [Uganda hypertension guideline]" in answer
    assert "3. [Hypertension treatment review]" in answer
    assert "[1](https://www.who.int/hypertension-guideline" in answer
    assert "[2](https://health.go.ug/hypertension" in answer
    assert "[3](https://pubmed.ncbi.nlm.nih.gov/123/" in answer
    assert "Hypertension medication evidence" not in answer
    assert "Duplicate hypertension" not in answer


def test_quick_response_uses_uncited_model_fallback_when_live_evidence_empty(monkeypatch):
    retrieval_calls = []

    async def fake_search_retrieval_queries(**kwargs):
        retrieval_calls.append(kwargs)
        return {"items": [], "provider_errors": ["timeout"], "timings_ms": {}}

    async def fake_post_model_response(payload, timeout_seconds):
        if payload["prompt_type"] == "empirico_quick_search_no_references":
            assert "first-line antihypertensive medication" in payload["prompt"]
            return {
                "answer": (
                    "When the evidence retriever is unavailable, provide a cautious answer "
                    "and tell the user to verify it against a current local guideline."
                ),
                "diagnosis_complete": True,
            }
        if payload["prompt_type"] == "empirico_quick_answer_detail_expansion":
            return {
                "answer": (
                    "When drug treatment is indicated, use a guideline-supported first-line antihypertensive option "
                    "rather than assuming one drug class fits all adults with stage 1 hypertension [1].\n\n"
                    "A quick answer should still check patient factors such as pregnancy, kidney disease, diabetes, "
                    "electrolyte risk, cough or angioedema history, oedema, drug interactions, and local availability "
                    "before selecting the exact medicine [1]."
                ),
                "diagnosis_complete": True,
            }
        assert payload["prompt_type"] == "empirico_quick_search"
        assert "AVAILABLE SOURCES:" in payload["prompt"]
        assert "EVIDENCE BASE:" in payload["prompt"]
        assert "[1]" in payload["prompt"]
        return {
            "answer": "When drug treatment is indicated, use a guideline-supported first-line antihypertensive option and adjust for patient factors [1].",
            "diagnosis_complete": True,
        }

    monkeypatch.setenv("EMPIRICO_FOLLOWUP_MODE", "off")
    monkeypatch.setenv("EMPIRICO_QUICK_ENABLE_RETRIEVAL_PLANNER", "false")
    monkeypatch.setenv("EMPIRICO_QUICK_EVIDENCE_PROVIDER_MODE", "crawl")
    monkeypatch.setattr(
        "healthnavi.services.evidence_retrieval_adapter._search_retrieval_queries",
        fake_search_retrieval_queries,
    )
    monkeypatch.setattr(
        "healthnavi.services.evidence_retrieval_adapter._post_model_response",
        fake_post_model_response,
    )

    answer, complete, prompt_type, followups = asyncio.run(
        generate_model_service_response(
            query="What is the first-line antihypertensive medication for stage 1 hypertension?",
            chat_history="",
            patient_data="",
            deep_search=False,
        )
    )

    assert len(retrieval_calls) == 2
    assert retrieval_calls[1]["provider_mode"] == "web"
    assert "couldn't retrieve" not in answer.lower()
    assert "try again" not in answer.lower()
    assert "**References**" not in answer
    assert complete is True
    assert prompt_type == "empirico_quick_search"
    assert followups == []


def test_status_model_answer_raises_instead_of_stitching_evidence(monkeypatch):
    calls: list[str] = []

    async def fake_search_retrieval_queries(**kwargs):
        return {
            "items": [
                {
                    "source": "crawl4ai",
                    "title": "Hypertension guideline",
                    "url": "https://www.who.int/publications/i/item/9789240033986",
                    "journal_or_publisher": "WHO",
                    "year": 2025,
                    "snippet": (
                        "For adults with hypertension requiring pharmacological treatment, "
                        "use thiazide and thiazide-like agents, ACE inhibitors or ARBs, "
                        "or long-acting dihydropyridine calcium channel blockers as initial treatment."
                    ),
                    "evidence_type": "guideline",
                    "raw": {"retrieval_mode": "static_html"},
                }
            ],
            "provider_errors": [],
            "timings_ms": {},
        }

    async def fake_post_model_response(payload, timeout_seconds):
        calls.append(payload["prompt_type"])
        return {"answer": "The model service is temporarily busy. Please try again."}

    async def no_sleep(_seconds):
        return None

    monkeypatch.setenv("EMPIRICO_FOLLOWUP_MODE", "off")
    monkeypatch.setenv("EMPIRICO_QUICK_ENABLE_RETRIEVAL_PLANNER", "false")
    monkeypatch.setattr(
        "healthnavi.services.evidence_retrieval_adapter._search_retrieval_queries",
        fake_search_retrieval_queries,
    )
    monkeypatch.setattr(
        "healthnavi.services.evidence_retrieval_adapter._post_model_response",
        fake_post_model_response,
    )
    monkeypatch.setattr("healthnavi.services.evidence_retrieval_adapter.asyncio.sleep", no_sleep)

    with pytest.raises(AnswerGenerationError):
        asyncio.run(
            generate_model_service_response(
                query="What is the first-line antihypertensive medication for stage 1 hypertension?",
                chat_history="",
                patient_data="",
                deep_search=False,
            )
        )

    # One retry, then give up: raw evidence text is never shown as if it were an answer.
    assert calls == ["empirico_quick_search", "empirico_quick_search"]


def test_retrieval_query_planner_falls_back_to_user_question(monkeypatch):
    async def fake_post_model_response(payload, timeout_seconds):
        return {"answer": "not json"}

    monkeypatch.setattr(
        "healthnavi.services.evidence_retrieval_adapter._post_model_response",
        fake_post_model_response,
    )

    queries = asyncio.run(
        _retrieval_queries_for_request(
            query="What are the treatment options for severe malnutrition in children under 5?",
            patient_data="",
            chat_history="",
            deep_search=True,
        )
    )

    assert queries == (
        "What are the treatment options for severe malnutrition in children under 5?",
    )


def test_quick_and_deep_can_broaden_retrieval_with_generic_planner(monkeypatch):
    monkeypatch.delenv("EMPIRICO_QUICK_ENABLE_RETRIEVAL_PLANNER", raising=False)
    monkeypatch.delenv("EMPIRICO_DEEP_ENABLE_RETRIEVAL_PLANNER", raising=False)
    question = "How is uncomplicated malaria treated in adults?"

    async def fake_post_model_response(payload, timeout_seconds):
        assert payload["prompt_type"] == "empirico_retrieval_query_plan"
        return {
            "answer": (
                '{"queries":["standard initial treatment guideline",'
                '"adult treatment regimen","practical dosing details"]}'
            )
        }

    monkeypatch.setattr(
        "healthnavi.services.evidence_retrieval_adapter._post_model_response",
        fake_post_model_response,
    )

    quick_queries = asyncio.run(
        _retrieval_queries_for_request(
            query=question,
            patient_data="",
            chat_history="",
            deep_search=False,
        )
    )
    deep_queries = asyncio.run(
        _retrieval_queries_for_request(
            query=question,
            patient_data="",
            chat_history="",
            deep_search=True,
        )
    )

    assert quick_queries == (
        question,
        "standard initial treatment guideline",
        "adult treatment regimen",
    )
    assert deep_queries == (
        question,
        "standard initial treatment guideline",
        "adult treatment regimen",
        "practical dosing details",
    )


def test_fallback_retrieval_queries_are_neutral_and_do_not_guess_answers(monkeypatch):
    monkeypatch.setenv("EMPIRICO_QUICK_ENABLE_RETRIEVAL_PLANNER", "false")
    cases = [
        (
            "What is recommended first-line ART for adults with HIV?",
            {"dolutegravir", "tenofovir", "lamivudine", "emtricitabine", "tdf", "3tc"},
        ),
        (
            "According to WHO malaria guidelines, how should malaria in pregnancy be treated?",
            {"artemisinin", "artesunate", "sulfadoxine", "pyrimethamine", "iptp"},
        ),
        (
            "What is the standard initial treatment regimen for drug-susceptible pulmonary tuberculosis?",
            {"isoniazid", "rifampicin", "pyrazinamide", "ethambutol", "hrze"},
        ),
    ]

    for question, forbidden_terms in cases:
        queries = asyncio.run(
            _retrieval_queries_for_request(
                query=question,
                patient_data="",
                chat_history="",
                deep_search=False,
            )
        )
        joined = " ".join(queries).lower()

        assert queries == (question,)
        assert not any(term in joined for term in forbidden_terms)


def test_retrieval_planner_auto_is_generic_not_condition_triggered(monkeypatch):
    monkeypatch.setenv("EMPIRICO_QUICK_ENABLE_RETRIEVAL_PLANNER", "auto")

    assert _retrieval_planner_enabled(False)

    monkeypatch.setenv("EMPIRICO_DEEP_ENABLE_RETRIEVAL_PLANNER", "auto")

    assert _retrieval_planner_enabled(True)

    monkeypatch.setenv("EMPIRICO_DEEP_ENABLE_RETRIEVAL_PLANNER", "true")

    assert _retrieval_planner_enabled(True)

    monkeypatch.setenv("EMPIRICO_QUICK_ENABLE_RETRIEVAL_PLANNER", "false")

    assert not _retrieval_planner_enabled(False)


def test_quick_mode_uses_bounded_retrieval_settings(monkeypatch):
    monkeypatch.setenv("EMPIRICO_QUICK_SEARCH_TOP_K", "9")
    monkeypatch.setenv("EMPIRICO_QUICK_ANSWER_TOP_K", "3")
    monkeypatch.setenv("EMPIRICO_QUICK_RETRIEVAL_TIME_BUDGET_SECONDS", "12.25")
    monkeypatch.setenv("EMPIRICO_QUICK_CRAWL_TIME_BUDGET_SECONDS", "10.25")
    monkeypatch.setenv("EMPIRICO_QUICK_REQUEST_TIMEOUT_SECONDS", "12")
    monkeypatch.setenv("EMPIRICO_QUICK_CRAWL_MAX_SOURCES", "6")
    monkeypatch.setenv("EMPIRICO_QUICK_CRAWL_MAX_PAGES", "8")
    monkeypatch.setenv("EMPIRICO_QUICK_MAX_RESULTS_PER_PROVIDER", "5")
    monkeypatch.delenv("EMPIRICO_QUICK_MAX_OUTPUT_TOKENS", raising=False)
    get_settings.cache_clear()

    settings = _search_settings_for_mode(False)
    get_settings.cache_clear()

    assert settings.retrieval_time_budget_seconds == 12.25
    assert settings.crawl_time_budget_seconds == 10.25
    assert settings.request_timeout_seconds == 12
    assert settings.crawl_max_sources == 6
    assert settings.crawl_max_pages == 8
    assert settings.max_results_per_provider == 5
    assert _answer_top_k(False) == 4
    assert _answer_top_k(True) == 8
    assert _evidence_search_top_k(False) == 9
    assert _max_output_tokens_for_mode(False) == 2000


def test_multi_branch_plan_disables_quick_retrieval_early_stop(monkeypatch):
    calls: list[str] = []

    async def fake_search_local_evidence(**kwargs):
        calls.append(kwargs["query"])
        return {
            "items": [
                {
                    "source": "crawl4ai",
                    "title": "Clinical guideline",
                    "url": f"https://example.org/{len(calls)}",
                    "snippet": "Clinical treatment guidance.",
                    "evidence_type": "guideline",
                }
                for _ in range(4)
            ],
            "provider_errors": [],
            "timings_ms": {},
        }

    monkeypatch.setenv("EMPIRICO_QUICK_RETRIEVAL_EARLY_STOP", "true")
    monkeypatch.setattr(
        "healthnavi.services.evidence_retrieval_adapter._search_local_evidence",
        fake_search_local_evidence,
    )
    asyncio.run(
        _search_retrieval_queries(
            queries=("first branch", "second branch"),
            top_k=8,
            country_code=None,
            deep_search=False,
            answer_top_k=4,
            coverage_required=True,
        )
    )

    assert calls == ["first branch", "second branch"]


def test_quick_mode_ignores_stale_tiny_retrieval_overrides(monkeypatch):
    monkeypatch.setenv("RETRIEVAL_TIME_BUDGET_SECONDS", "16")
    monkeypatch.setenv("CRAWL_TIME_BUDGET_SECONDS", "14")
    monkeypatch.setenv("REQUEST_TIMEOUT_SECONDS", "20")
    monkeypatch.setenv("CRAWL_MAX_SOURCES", "8")
    monkeypatch.setenv("CRAWL_MAX_PAGES", "14")
    monkeypatch.setenv("MAX_RESULTS_PER_PROVIDER", "10")
    monkeypatch.setenv("EMPIRICO_QUICK_RETRIEVAL_TIME_BUDGET_SECONDS", "4.4")
    monkeypatch.setenv("EMPIRICO_QUICK_CRAWL_TIME_BUDGET_SECONDS", "4")
    monkeypatch.setenv("EMPIRICO_QUICK_REQUEST_TIMEOUT_SECONDS", "4")
    monkeypatch.setenv("EMPIRICO_QUICK_CRAWL_MAX_SOURCES", "4")
    monkeypatch.setenv("EMPIRICO_QUICK_CRAWL_MAX_PAGES", "6")
    monkeypatch.setenv("EMPIRICO_QUICK_MAX_RESULTS_PER_PROVIDER", "4")
    get_settings.cache_clear()

    settings = _search_settings_for_mode(False)
    get_settings.cache_clear()

    assert settings.retrieval_time_budget_seconds == 10
    assert settings.crawl_time_budget_seconds == 8
    assert settings.request_timeout_seconds == 12
    assert settings.crawl_max_sources == 4
    assert settings.crawl_max_pages == 8
    assert settings.max_results_per_provider == 4


def test_quick_mode_uses_base_retrieval_settings_when_mode_overrides_absent(monkeypatch):
    for key in (
        "EMPIRICO_QUICK_RETRIEVAL_TIME_BUDGET_SECONDS",
        "EMPIRICO_QUICK_CRAWL_TIME_BUDGET_SECONDS",
        "EMPIRICO_QUICK_REQUEST_TIMEOUT_SECONDS",
        "EMPIRICO_QUICK_CRAWL_MAX_SOURCES",
        "EMPIRICO_QUICK_CRAWL_MAX_PAGES",
        "EMPIRICO_QUICK_MAX_RESULTS_PER_PROVIDER",
    ):
        monkeypatch.setenv(key, "")
    monkeypatch.setenv("RETRIEVAL_TIME_BUDGET_SECONDS", "16")
    monkeypatch.setenv("CRAWL_TIME_BUDGET_SECONDS", "14")
    monkeypatch.setenv("REQUEST_TIMEOUT_SECONDS", "20")
    monkeypatch.setenv("CRAWL_MAX_SOURCES", "6")
    monkeypatch.setenv("CRAWL_MAX_PAGES", "10")
    monkeypatch.setenv("MAX_RESULTS_PER_PROVIDER", "10")
    get_settings.cache_clear()

    settings = _search_settings_for_mode(False)
    get_settings.cache_clear()

    assert settings.retrieval_time_budget_seconds == 10
    assert settings.crawl_time_budget_seconds == 8
    assert settings.request_timeout_seconds == 12
    assert settings.crawl_max_sources == 4
    assert settings.crawl_max_pages == 8
    assert settings.max_results_per_provider == 4


def test_retrieval_defaults_allow_web_crawl_to_finish():
    settings = EvidenceRetrievalSettings()

    assert settings.retrieval_time_budget_seconds == 18
    assert settings.crawl_time_budget_seconds == 14


def test_model_timeout_uses_per_mode_defaults_when_override_absent(monkeypatch):
    monkeypatch.setenv("EMPIRICO_QUICK_MODEL_TIMEOUT_SECONDS", "")
    monkeypatch.setenv("EMPIRICO_DEEP_MODEL_TIMEOUT_SECONDS", "")
    monkeypatch.setenv("MODEL_SERVICE_TIMEOUT_SECONDS", "180")

    assert _model_timeout_for_mode(False) == 30
    assert _model_timeout_for_mode(True) == 120


def test_model_timeout_mode_override_is_capped_by_global_timeout(monkeypatch):
    monkeypatch.setenv("MODEL_SERVICE_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("EMPIRICO_QUICK_MODEL_TIMEOUT_SECONDS", "60")

    assert _model_timeout_for_mode(False) == 45


def test_model_timeout_ignores_stale_tiny_mode_overrides(monkeypatch):
    monkeypatch.setenv("MODEL_SERVICE_TIMEOUT_SECONDS", "180")
    monkeypatch.setenv("EMPIRICO_QUICK_MODEL_TIMEOUT_SECONDS", "4.7")
    monkeypatch.setenv("EMPIRICO_DEEP_MODEL_TIMEOUT_SECONDS", "8")

    assert _model_timeout_for_mode(False) == 30
    assert _model_timeout_for_mode(True) == 120


def test_local_followups_avoid_second_model_call_for_dosage_questions():
    followups = _local_followup_questions(
        "Calculate the dose for ceftriaxone for a 60kg adult with severe pneumonia",
        "Adults receive ceftriaxone 1 g once daily [1].",
    )

    assert len(followups) == 3
    assert "alternatives" in followups[0].lower()


def test_model_service_response_normalizes_common_gcp_envelopes():
    assert _normalize_model_service_response(
        {"data": {"model_response": "Use current WHO guidance [1]."}}
    )["answer"] == "Use current WHO guidance [1]."
    assert _normalize_model_service_response(
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "Follow current guideline recommendations [1]."}
                        ]
                    }
                }
            ]
        }
    )["answer"] == "Follow current guideline recommendations [1]."


def test_service_status_answers_are_not_treated_as_medical_answers():
    assert _answer_looks_like_service_status(
        "The model service is temporarily busy. Please try again."
    )
    assert not _answer_looks_like_service_status(
        "Start antiretroviral therapy promptly after confirming HIV diagnosis."
    )


def test_html_citations_use_text_fragment_when_no_page_is_available():
    item = {
        "source": "crawl4ai",
        "title": "Hypertension pharmacological treatment guideline",
        "url": "https://www.who.int/publications/i/item/9789240033986",
        "snippet": (
            "For adults with hypertension requiring pharmacological treatment, use a "
            "thiazide-like diuretic, an ACE inhibitor or ARB, or a long-acting calcium channel blocker."
        ),
        "journal_or_publisher": "WHO",
        "evidence_type": "guideline",
        "raw": {"retrieval_mode": "static_html"},
    }

    citations = _citations_from_evidence([item])

    assert "#:~:text=" in str(citations[0]["url"])
    assert "For%20adults%20with%20hypertension" in str(citations[0]["url"])


def test_query_focused_snippet_prefers_direct_answer_segments_for_practical_query():
    snippet = _query_focused_snippet(
        (
            "Malaria in pregnancy can lead to stillbirth and low birth weight. "
            "Prevention includes insecticide-treated mosquito nets and intermittent preventive treatment. "
            "Confirmed uncomplicated malaria in pregnancy should receive prompt effective antimalarial treatment. "
            "Severe malaria in pregnancy requires urgent parenteral antimalarial therapy."
        ),
        "According to WHO malaria guidelines, how should malaria in pregnancy be treated?",
        500,
    )

    assert "Confirmed uncomplicated malaria" in snippet
    assert "Severe malaria in pregnancy requires" in snippet


def test_treatment_query_ranking_downranks_prevention_only_sources(monkeypatch):
    monkeypatch.setenv("EMPIRICO_EVIDENCE_PROVIDER_MODE", "web")
    items = [
        {
            "source": "crawl4ai",
            "title": "Intermittent preventive treatment of malaria in pregnancy",
            "url": "https://www.who.int/malaria-prevention-pregnancy",
            "snippet": "Pregnant women should use mosquito nets and receive IPTp to prevent malaria.",
            "evidence_type": "guideline",
            "raw": {"retrieval_mode": "static_html"},
        },
        {
            "source": "crawl4ai",
            "title": "Guidelines for the treatment of malaria in pregnancy",
            "url": "https://www.who.int/malaria-treatment-pregnancy",
            "snippet": "Confirmed malaria in pregnancy should be treated with prompt effective antimalarial therapy.",
            "evidence_type": "guideline",
            "raw": {"retrieval_mode": "static_html"},
        },
    ]

    filtered = _filter_evidence_items(
        items,
        query="According to WHO malaria guidelines, how should malaria in pregnancy be treated?",
    )

    assert [item["title"] for item in filtered] == [
        "Guidelines for the treatment of malaria in pregnancy",
        "Intermittent preventive treatment of malaria in pregnancy",
    ]


def test_quick_retrieval_does_not_early_stop_on_tangential_first_results(monkeypatch):
    calls: list[str] = []
    first_query = "national clinical policy implementation"
    second_query = "malaria pregnancy treatment"

    async def fake_search_local_evidence(**kwargs):
        calls.append(kwargs["query"])
        if kwargs["query"] == first_query:
            items = [
                {
                    "source": "crawl4ai",
                    "title": f"Broad health systems source {index}",
                    "url": f"https://example.org/broad-{index}",
                    "journal_or_publisher": "Guideline",
                    "snippet": "This implementation document covers service delivery planning and reporting workflows.",
                    "evidence_type": "guideline",
                    "raw": {"retrieval_mode": "static_html"},
                }
                for index in range(1, 5)
            ]
        else:
            items = [
                {
                    "source": "crawl4ai",
                    "title": "Malaria pregnancy treatment guideline",
                    "url": "https://example.org/treatment",
                    "journal_or_publisher": "Guideline",
                    "snippet": "Confirmed malaria in pregnancy should be treated with prompt effective antimalarial therapy.",
                    "evidence_type": "guideline",
                    "raw": {"retrieval_mode": "static_html"},
                }
            ]
        return {"items": items, "provider_errors": [], "timings_ms": {"total": 10.0}}

    monkeypatch.setenv("EMPIRICO_QUICK_RETRIEVAL_EARLY_STOP", "true")
    monkeypatch.setattr(
        "healthnavi.services.evidence_retrieval_adapter._search_local_evidence",
        fake_search_local_evidence,
    )

    result = asyncio.run(
        _search_retrieval_queries(
            queries=(first_query, second_query),
            top_k=8,
            country_code=None,
            deep_search=False,
            source_preference_terms=(),
            answer_top_k=4,
        )
    )

    assert calls == [first_query, second_query]
    assert "query_2" in result["timings_ms"]


def test_citations_recover_provider_url_aliases_and_url_ids():
    alias_item = {
        "source": "crawl4ai",
        "title": "Hypertension guideline",
        "snippet": "Initial treatment guidance for hypertension.",
        "evidence_type": "guideline",
        "raw": {
            "canonical_url": "https://www.who.int/publications/i/item/9789240033986",
            "publisher": "WHO",
            "publication_year": 2025,
        },
    }
    id_item = {
        "id": "crawl4ai:https://health.go.ug/downloads/hypertension",
        "source": "crawl4ai",
        "title": "Uganda hypertension guidance",
        "snippet": "Uganda hypertension treatment guidance.",
        "evidence_type": "guideline",
    }

    citations = _citations_from_evidence([alias_item, id_item])

    assert citations[0]["url"] == "https://www.who.int/publications/i/item/9789240033986"
    assert citations[0]["source_label"] == "WHO"
    assert citations[0]["year"] == 2025
    assert citations[1]["url"] == "https://health.go.ug/downloads/hypertension"


def test_web_mode_filters_unsupported_and_seed_references(monkeypatch):
    monkeypatch.setenv("EMPIRICO_EVIDENCE_PROVIDER_MODE", "web")
    items = [
        {
            "source": "legacy_vector",
            "title": "Unsupported old reference",
            "url": "https://example.org/static",
        },
        {
            "source": "semantic_scholar",
            "title": "Scholar article",
            "url": "https://www.semanticscholar.org/paper/example",
        },
        {
            "source": "pubmed",
            "title": "Current review",
            "url": "https://pubmed.ncbi.nlm.nih.gov/123",
        },
        {
            "source": "crawl4ai",
            "title": "Catalog PDF seed",
            "url": "https://example.org/catalog.pdf",
            "raw": {"retrieval_mode": "pdf_seed_metadata"},
        },
        {
            "source": "crawl4ai",
            "title": "Crawled guideline page",
            "url": "https://example.org/guideline",
            "raw": {"retrieval_mode": "static_html"},
        },
        {
            "source": "official_health_api",
            "title": "Official public health page",
            "url": "https://www.who.int/example",
        },
    ]

    filtered = _filter_evidence_items(items)

    assert [item["title"] for item in filtered] == [
        "Official public health page",
        "Current review",
        "Scholar article",
        "Crawled guideline page",
    ]


def test_crawl_mode_keeps_only_real_crawl_and_official_sources(monkeypatch):
    monkeypatch.setenv("EMPIRICO_EVIDENCE_PROVIDER_MODE", "crawl")
    items = [
        {
            "source": "semantic_scholar",
            "title": "Scholar article",
            "url": "https://www.semanticscholar.org/paper/example",
        },
        {
            "source": "crawl4ai",
            "title": "Catalog PDF seed",
            "url": "https://example.org/catalog.pdf",
            "raw": {"retrieval_mode": "pdf_seed_metadata"},
        },
        {
            "source": "crawl4ai",
            "title": "Crawled guideline page",
            "url": "https://example.org/guideline",
            "raw": {"retrieval_mode": "browser"},
        },
        {
            "source": "official_health_api",
            "title": "Official public health page",
            "url": "https://www.who.int/example",
        },
    ]

    filtered = _filter_evidence_items(items)

    assert [item["title"] for item in filtered] == [
        "Official public health page",
        "Crawled guideline page",
    ]


def test_seed_metadata_fallback_keeps_only_trusted_relevant_crawl_links(monkeypatch):
    monkeypatch.setenv("EMPIRICO_EVIDENCE_PROVIDER_MODE", "web")
    items = [
        {
            "source": "crawl4ai",
            "title": "Uganda integrated management of malaria practical guide",
            "url": "https://platform.who.int/docs/default-source/mca-documents/policy-documents/operational-guidance/UGA-CH-33-01-OPERATIONAL-GUIDANCE-2012-eng-Manual-integrated-management-of-malaria.pdf",
            "raw": {"retrieval_mode": "pdf_seed_metadata"},
        },
        {
            "source": "crawl4ai",
            "title": "Uganda nutrition guideline",
            "url": "https://platform.who.int/docs/default-source/example.pdf",
            "raw": {"retrieval_mode": "pdf_seed_metadata"},
        },
        {
            "source": "crawl4ai",
            "title": "Malaria pregnancy blog",
            "url": "https://example.com/malaria-pregnancy.pdf",
            "raw": {"retrieval_mode": "pdf_seed_metadata"},
        },
    ]

    filtered = _filter_evidence_items(
        items,
        query="severe malaria in pregnancy treatment in Uganda",
        source_preference_terms=("uganda", "platform.who.int", "africa"),
        allow_seed_metadata=True,
    )

    assert [item["title"] for item in filtered] == [
        "Uganda integrated management of malaria practical guide",
    ]


def test_treatment_queries_drop_public_health_indicator_feeds(monkeypatch):
    monkeypatch.setenv("EMPIRICO_EVIDENCE_PROVIDER_MODE", "web")
    items = [
        {
            "source": "official_health_api",
            "title": "WHO GHO indicator: IPTp3 coverage",
            "url": "https://ghoapi.azureedge.net/api/MALARIA_IPTP3_COVERAGE",
        },
        {
            "source": "semantic_scholar",
            "title": "Severe malaria in pregnancy clinical review",
            "url": "https://www.semanticscholar.org/paper/example",
            "abstract": "Treatment of severe malaria in pregnancy.",
        },
    ]

    filtered = _filter_evidence_items(
        items,
        query="severe malaria in pregnancy treatment",
    )

    assert [item["title"] for item in filtered] == [
        "Severe malaria in pregnancy clinical review",
    ]


def test_official_health_api_query_tokens_drop_generic_question_words():
    assert _official_health_api_query_tokens(
        "What is the standard initial treatment regimen for drug-susceptible pulmonary tuberculosis?"
    ) == [
        "treatment",
        "regimen",
        "drug",
        "susceptible",
        "pulmonary",
        "tuberculosis",
    ]


def test_clinical_queries_drop_indicators_and_zero_overlap_crawl_pages(monkeypatch):
    monkeypatch.setenv("EMPIRICO_EVIDENCE_PROVIDER_MODE", "web")
    items = [
        {
            "source": "official_health_api",
            "title": "World Bank indicator: Adults newly infected with HIV",
            "url": "https://api.worldbank.org/v2/country/UGA/indicator/SH.HIV.INCD",
            "evidence_type": "official_indicator",
        },
        {
            "source": "crawl4ai",
            "title": "Guidelines for the treatment of malaria",
            "url": "https://example.org/wrong-document.pdf",
            "snippet": "General WHO disclaimer and breast examination text for adult women.",
            "evidence_type": "guideline",
            "raw": {"retrieval_mode": "linked_pdf_text"},
        },
        {
            "source": "crawl4ai",
            "title": "HIV treatment recommendations",
            "url": "https://www.who.int/hiv-treatment",
            "snippet": "HIV antiretroviral treatment recommendations for adults.",
            "evidence_type": "guideline",
            "raw": {"retrieval_mode": "static_html"},
        },
    ]

    filtered = _filter_evidence_items(
        items,
        query="What is recommended first-line ART for adults with HIV?",
    )

    assert [item["title"] for item in filtered] == [
        "HIV treatment recommendations",
    ]


def test_filter_evidence_does_not_special_case_acronyms(monkeypatch):
    monkeypatch.setenv("EMPIRICO_EVIDENCE_PROVIDER_MODE", "web")
    items = [
        {
            "source": "crawl4ai",
            "title": "WHO Guidelines",
            "url": "https://iris.who.int/example",
            "snippet": "Treatment guidance developed by experts from Kampala, Uganda.",
            "evidence_type": "guideline",
            "raw": {"retrieval_mode": "linked_pdf_text"},
        },
        {
            "source": "crawl4ai",
            "title": "HIV treatment recommendations",
            "url": "https://www.who.int/hiv-treatment",
            "snippet": "HIV antiretroviral treatment recommendations for adults.",
            "evidence_type": "guideline",
            "raw": {"retrieval_mode": "static_html"},
        },
    ]

    filtered = _filter_evidence_items(
        items,
        query="HIV treatment guidelines Kampala Uganda",
    )

    assert {item["title"] for item in filtered} == {
        "WHO Guidelines",
        "HIV treatment recommendations",
    }


def test_statistics_queries_keep_public_health_indicator_feeds(monkeypatch):
    monkeypatch.setenv("EMPIRICO_EVIDENCE_PROVIDER_MODE", "web")
    items = [
        {
            "source": "official_health_api",
            "title": "WHO GHO indicator: IPTp3 coverage",
            "url": "https://ghoapi.azureedge.net/api/MALARIA_IPTP3_COVERAGE",
        },
    ]

    filtered = _filter_evidence_items(
        items,
        query="What is IPTp coverage in Uganda?",
    )

    assert [item["title"] for item in filtered] == [
        "WHO GHO indicator: IPTp3 coverage",
    ]


def test_web_mode_keeps_explicit_uganda_sources_without_local_default(monkeypatch):
    monkeypatch.setenv("EMPIRICO_EVIDENCE_PROVIDER_MODE", "web")
    items = [
        {
            "source": "official_health_api",
            "title": "Intermittent preventive treatment of malaria in pregnancy",
            "url": "https://api.worldbank.org/v2/country/UGA/indicator/example",
        },
        {
            "source": "semantic_scholar",
            "title": "Treating Severe Malaria in Pregnancy: A Review of the Evidence",
            "url": "https://www.semanticscholar.org/paper/africa",
            "abstract": "Evidence from African malaria-endemic settings.",
        },
        {
            "source": "crawl4ai",
            "title": "Uganda severe malaria in pregnancy guideline page",
            "url": "https://health.go.ug/severe-malaria-pregnancy",
            "snippet": "Uganda Ministry of Health guidance on severe malaria in pregnancy.",
            "raw": {"retrieval_mode": "static_html"},
        },
    ]

    filtered = _filter_evidence_items(
        items,
        source_preference_terms=(
            "uganda",
            "health.go.ug",
            "ministry of health uganda",
            "africa",
        ),
    )

    assert [item["title"] for item in filtered] == [
        "Uganda severe malaria in pregnancy guideline page",
        "Intermittent preventive treatment of malaria in pregnancy",
        "Treating Severe Malaria in Pregnancy: A Review of the Evidence",
    ]


def test_guideline_trust_outranks_broad_source_preference_terms(monkeypatch):
    monkeypatch.setenv("EMPIRICO_EVIDENCE_PROVIDER_MODE", "web")
    items = [
        {
            "source": "semantic_scholar",
            "title": "Severe malnutrition treatment trial in Africa",
            "url": "https://www.semanticscholar.org/paper/example",
            "abstract": "Evidence from African severe malnutrition programmes.",
            "evidence_type": "guideline",
        },
        {
            "source": "crawl4ai",
            "title": "Guideline: updates on the management of severe acute malnutrition in infants and children",
            "url": "https://www.who.int/publications-detail-redirect/9789241506328",
            "snippet": "WHO guideline on severe acute malnutrition in infants and children.",
            "evidence_type": "guideline",
            "raw": {"retrieval_mode": "static_html"},
        },
    ]

    filtered = _filter_evidence_items(
        items,
        query="treatment options for severe malnutrition in children",
        source_preference_terms=("africa",),
    )

    assert filtered[0]["title"].startswith("Guideline: updates")


def test_filter_evidence_prefers_more_recent_equivalent_guideline(monkeypatch):
    monkeypatch.setenv("EMPIRICO_EVIDENCE_PROVIDER_MODE", "web")
    items = [
        {
            "source": "crawl4ai",
            "title": "Hypertension pharmacological treatment guideline",
            "url": "https://www.who.int/publications/older-hypertension-guideline",
            "snippet": "First-line hypertension treatment includes thiazide-like agents, ACE inhibitors, ARBs, or long-acting calcium channel blockers.",
            "evidence_type": "guideline",
            "year": 2021,
            "raw": {"retrieval_mode": "static_html"},
        },
        {
            "source": "crawl4ai",
            "title": "Hypertension pharmacological treatment guideline",
            "url": "https://www.who.int/publications/current-hypertension-guideline",
            "snippet": "First-line hypertension treatment includes thiazide-like agents, ACE inhibitors, ARBs, or long-acting calcium channel blockers.",
            "evidence_type": "guideline",
            "year": 2025,
            "raw": {"retrieval_mode": "static_html"},
        },
    ]

    filtered = _filter_evidence_items(
        items,
        query="What is the first-line antihypertensive medication for stage 1 hypertension?",
        source_preference_terms=(),
    )

    assert filtered[0]["url"] == "https://www.who.int/publications/current-hypertension-guideline"


def test_filter_evidence_orders_local_guidance_then_recent_global_sources(monkeypatch):
    monkeypatch.setenv("EMPIRICO_EVIDENCE_PROVIDER_MODE", "web")
    preference_terms = ("uganda", "health.go.ug", "ministry of health uganda", "who afro", "africa")
    items = [
        {
            "source": "crawl4ai",
            "title": "WHO older hypertension guideline",
            "url": "https://www.who.int/publications/older-hypertension-guideline",
            "snippet": "Hypertension and antihypertensive treatment guidance.",
            "evidence_type": "guideline",
            "year": 2021,
            "raw": {"retrieval_mode": "static_html"},
        },
        {
            "source": "crawl4ai",
            "title": "Uganda hypertension guideline",
            "url": "https://health.go.ug/hypertension",
            "snippet": "Ministry of Health Uganda hypertension treatment guidance.",
            "evidence_type": "guideline",
            "year": 2023,
            "raw": {"retrieval_mode": "static_html"},
        },
        {
            "source": "crawl4ai",
            "title": "WHO current hypertension guideline",
            "url": "https://www.who.int/publications/current-hypertension-guideline",
            "snippet": "Hypertension and antihypertensive treatment guidance.",
            "evidence_type": "guideline",
            "year": 2025,
            "raw": {"retrieval_mode": "static_html"},
        },
    ]

    filtered = _filter_evidence_items(
        items,
        query="What is the first-line antihypertensive medication?",
        source_preference_terms=preference_terms,
    )

    assert [item["title"] for item in filtered] == [
        "Uganda hypertension guideline",
        "WHO current hypertension guideline",
        "WHO older hypertension guideline",
    ]


def test_filter_evidence_prefers_direct_title_match_over_incidental_body_match(monkeypatch):
    monkeypatch.setenv("EMPIRICO_EVIDENCE_PROVIDER_MODE", "web")
    items = [
        {
            "source": "crawl4ai",
            "title": "WHO Guidelines",
            "url": "https://iris.who.int/server/api/core/bitstreams/unrelated/content",
            "snippet": (
                "This trusted guideline mentions first-line treatment and hypertension "
                "only in passing while discussing another disease area."
            ),
            "evidence_type": "clinical_resource",
            "raw": {"retrieval_mode": "static_pdf"},
        },
        {
            "source": "crawl4ai",
            "title": "Guideline for the pharmacological treatment of hypertension in adults",
            "url": "https://www.who.int/publications/i/item/9789240033986",
            "snippet": "Guideline overview for pharmacological treatment of hypertension in adults.",
            "evidence_type": "clinical_resource",
            "raw": {"retrieval_mode": "static_html"},
        },
    ]

    filtered = _filter_evidence_items(
        items,
        query="What is the first-line antihypertensive medication for stage 1 hypertension?",
        source_preference_terms=(),
    )

    assert filtered[0]["url"] == "https://www.who.int/publications/i/item/9789240033986"


def test_filter_evidence_drops_trusted_but_wrong_topic_sources(monkeypatch):
    monkeypatch.setenv("EMPIRICO_EVIDENCE_PROVIDER_MODE", "web")
    items = [
        {
            "source": "crawl4ai",
            "title": "Background review2",
            "url": "https://cdn.who.int/media/docs/default-source/nutritionlibrary/publications/malnutrition/guideline-updates-on-the-management-of-severe-acute-malnutrition-in-infants-and-children/review2.pdf",
            "snippet": "Severe acute malnutrition management in infants and children.",
            "evidence_type": "guideline",
            "raw": {"retrieval_mode": "linked_pdf_text", "publisher": "WHO"},
        },
        {
            "source": "crawl4ai",
            "title": "Guideline for the pharmacological treatment of hypertension in adults",
            "url": "https://iris.who.int/server/api/core/bitstreams/f062769d-f075-4a00-87af-0a2106e0bd04/content",
            "snippet": "First-line pharmacological treatment of hypertension in adults.",
            "evidence_type": "guideline",
            "raw": {"retrieval_mode": "linked_pdf_text", "publisher": "WHO"},
        },
    ]

    filtered = _filter_evidence_items(
        items,
        query="What is the first-line antihypertensive medication for stage 1 hypertension?",
        source_preference_terms=("uganda", "africa", "who afro"),
    )

    assert [item["title"] for item in filtered] == [
        "Guideline for the pharmacological treatment of hypertension in adults",
    ]


def test_filter_evidence_drops_local_fallback_sources_with_only_generic_overlap(monkeypatch):
    monkeypatch.setenv("EMPIRICO_EVIDENCE_PROVIDER_MODE", "web")
    items = [
        {
            "source": "crawl4ai",
            "title": "Guideline for the pharmacological treatment of hypertension in adults",
            "url": "https://iris.who.int/server/api/core/bitstreams/f062769d-f075-4a00-87af-0a2106e0bd04/content",
            "journal_or_publisher": "WHO",
            "snippet": (
                "For adults with hypertension requiring pharmacological treatment, use drugs "
                "from any of the following three classes as initial treatment: thiazide and "
                "thiazide-like agents, ACE inhibitors or ARBs, or long-acting dihydropyridine "
                "calcium channel blockers."
            ),
            "evidence_type": "guideline",
            "raw": {"retrieval_mode": "linked_pdf_text"},
        },
        {
            "source": "crawl4ai",
            "title": "Uganda Integrated Management of Acute Malnutrition Guidelines",
            "url": "https://platform.who.int/docs/default-source/uganda-imam-guideline.pdf",
            "journal_or_publisher": "Ministry of Health Uganda",
            "snippet": (
                "Children with severe acute malnutrition may reach this stage of treatment "
                "with shock, dehydration, and heart failure. Give oxygen and fluids as described."
            ),
            "evidence_type": "guideline",
            "raw": {"retrieval_mode": "pdf_text"},
        },
        {
            "source": "crawl4ai",
            "title": "WHO HIV updated recommendations",
            "url": "https://iris.who.int/server/api/core/bitstreams/hiv-guideline/content",
            "journal_or_publisher": "WHO",
            "snippet": (
                "People established on ART may have fewer medication refills; hypertension "
                "screening can be integrated into chronic care."
            ),
            "evidence_type": "guideline",
            "raw": {"retrieval_mode": "linked_pdf_text"},
        },
    ]

    filtered = _filter_evidence_items(
        items,
        query="What is the first-line antihypertensive medication for stage 1 hypertension?",
        source_preference_terms=("uganda", "ministry of health uganda", "africa"),
    )

    assert [item["title"] for item in filtered] == [
        "Guideline for the pharmacological treatment of hypertension in adults",
    ]




def test_answer_candidates_order_guidelines_first_and_cap_passages_per_document():
    from healthnavi.services.evidence_retrieval_adapter import _answer_candidates

    def crawl(title, url, snippet, score, page=None):
        item = {
            "source": "crawl4ai",
            "title": title,
            "url": f"{url}#page={page}" if page else url,
            "journal_or_publisher": "WHO",
            "snippet": snippet,
            "evidence_type": "clinical_resource",
            "final_score": score,
            "raw": {"retrieval_mode": "linked_pdf_text"},
        }
        return item

    who_pdf = "https://iris.who.int/bitstreams/abc/content"
    items = [
        {
            "source": "pubmed",
            "title": "Dyslipidemia among adults living with HIV on dolutegravir in Kampala, Uganda",
            "url": "https://pubmed.ncbi.nlm.nih.gov/1/",
            "journal_or_publisher": "PLoS One",
            "year": 2024,
            "abstract": "HIV treatment cohort in Kampala Uganda on dolutegravir based antiretroviral therapy.",
            "evidence_type": "journal_article",
            "final_score": 0.9,
        },
        crawl("Consolidated HIV guidelines", who_pdf, "HIV treatment: preferred first-line ART is TDF + 3TC + DTG.", 0.71, page=44),
        crawl("Consolidated HIV guidelines", who_pdf, "HIV treatment: second-line ART after failure.", 0.70, page=90),
        crawl("Consolidated HIV guidelines", who_pdf, "HIV treatment: monitoring viral load.", 0.69, page=120),
        crawl("Consolidated HIV guidelines", who_pdf, "HIV treatment: paediatric dosing tables.", 0.68, page=150),
        crawl("Consolidated HIV guidelines", who_pdf, "HIV treatment: preferred first-line ART is TDF + 3TC + DTG.", 0.60, page=44),
        {
            "source": "official_health_api",
            "title": "World Bank indicator: Adults newly infected with HIV",
            "url": "https://api.worldbank.org/v2/country/UGA/indicator/SH.HIV.INCD",
            "snippet": "Latest value: 38000 (2024)",
            "evidence_type": "official_indicator",
            "final_score": 0.75,
        },
    ]

    candidates = _answer_candidates(
        items,
        query="What is the first-line HIV treatment for an adult woman?",
        source_preference_terms=("uganda", "kampala"),
        deep_search=False,
    )

    titles = [(c["title"], c["url"]) for c in candidates]
    # WHO guideline passages come before the Kampala cohort study despite the place name.
    assert titles[0][0] == "Consolidated HIV guidelines"
    assert [title for title, _ in titles].index("Consolidated HIV guidelines") < next(
        index for index, (title, _) in enumerate(titles) if title.startswith("Dyslipidemia")
    )
    # Exact duplicate passage dropped and at most three passages per document kept.
    assert sum(1 for title, _ in titles if title == "Consolidated HIV guidelines") == 3
    assert f"{who_pdf}#page=150" not in [url for _, url in titles]
    # Statistics indicators are not offered for a treatment question.
    assert not any("World Bank" in title for title, _ in titles)


def test_answer_candidates_return_nothing_when_no_passage_matches_the_question():
    from healthnavi.services.evidence_retrieval_adapter import _answer_candidates

    items = [
        {
            "source": "crawl4ai",
            "title": "Ceftriaxone injectable",
            "url": "https://medicalguidelines.msf.org/ceftriaxone",
            "snippet": "Doses greater than 2 g should be given by IV infusion only.",
            "evidence_type": "guideline",
            "final_score": 0.5,
            "raw": {"retrieval_mode": "static_html"},
        },
        {
            "source": "official_health_api",
            "title": "World Bank indicator: Anti-malarial drug use by pregnant women",
            "url": "https://api.worldbank.org/v2/country/UGA/indicator/SH.MLR.SPFN.Q2.ZS",
            "snippet": "Latest value: 12 (2019)",
            "evidence_type": "official_indicator",
            "final_score": 0.7,
        },
    ]

    # Off-topic pages and statistics indicators are not offered to the model, so the
    # answer path falls through to rescue retrieval and then an uncited answer.
    candidates = _answer_candidates(
        items,
        query="Can I give metronidazole to a patient on warfarin?",
        source_preference_terms=(),
        deep_search=False,
    )

    assert candidates == []


def test_answer_sources_merge_passages_from_the_same_location():
    from healthnavi.services.evidence_retrieval_adapter import _answer_sources, _citations_from_evidence

    evidence = [
        {
            "source": "crawl4ai",
            "title": "Consolidated HIV guidelines",
            "url": "https://iris.who.int/x/content#page=23",
            "snippet": "First passage on page 23.",
            "evidence_type": "guideline",
            "raw": {"retrieval_mode": "linked_pdf_text", "page": 23},
        },
        {
            "source": "crawl4ai",
            "title": "Consolidated HIV guidelines",
            "url": "https://iris.who.int/x/content#page=23",
            "snippet": "Second passage on page 23.",
            "evidence_type": "guideline",
            "raw": {"retrieval_mode": "linked_pdf_text", "page": 23},
        },
        {
            "source": "crawl4ai",
            "title": "Consolidated HIV guidelines",
            "url": "https://iris.who.int/x/content#page=24",
            "snippet": "Passage on page 24.",
            "evidence_type": "guideline",
            "raw": {"retrieval_mode": "linked_pdf_text", "page": 24},
        },
    ]
    citations = _citations_from_evidence(evidence)
    assert len(citations) == 3

    sources = _answer_sources(evidence, citations, deep_search=False, query="HIV first-line ART")

    assert [s["number"] for s in sources] == [1, 2]
    assert sources[0]["url"].endswith("#page=23")
    assert "First passage on page 23. [...] Second passage on page 23." == sources[0]["excerpt"]
    assert sources[1]["excerpt"] == "Passage on page 24."
    assert "same_document_as" not in sources[0]
    assert sources[1]["same_document_as"] == 1


def test_answer_candidates_limit_distinct_documents_to_reference_cap_plus_two(monkeypatch):
    from healthnavi.services.evidence_retrieval_adapter import _answer_candidates, _max_references

    monkeypatch.delenv("EMPIRICO_QUICK_MAX_REFERENCES", raising=False)
    monkeypatch.delenv("EMPIRICO_QUICK_CONTEXT_SOURCES", raising=False)
    assert _max_references(False) == 4
    assert _max_references(True) == 8

    items = [
        {
            "source": "crawl4ai",
            "title": f"Malaria guideline {index}",
            "url": f"https://iris.who.int/malaria-{index}",
            "snippet": "Severe malaria treatment: IV artesunate first, then oral ACT.",
            "evidence_type": "guideline",
            "final_score": 0.9 - index / 100,
            "raw": {"retrieval_mode": "static_html"},
        }
        for index in range(10)
    ]

    candidates = _answer_candidates(
        items,
        query="treatment of severe malaria",
        source_preference_terms=(),
        deep_search=False,
    )

    assert len(candidates) == 6
    assert [c["title"] for c in candidates] == [f"Malaria guideline {index}" for index in range(6)]


def test_document_year_falls_back_to_the_year_named_in_the_title_or_url():
    from healthnavi.services.evidence_retrieval_adapter import _document_year

    # Metadata year wins when present.
    assert _document_year({"title": "Some guideline 2016", "url": "https://x/y", "year": 2024}) == 2024
    # Otherwise the latest year in the title or URL path.
    assert (
        _document_year(
            {
                "title": "Uganda Clinical Guidelines",
                "url": "https://www.differentiatedservicedelivery.org/wp-content/uploads/UCG-2023-Publication-Final-PDF-Version-1.pdf",
            }
        )
        == 2023
    )
    assert (
        _document_year(
            {
                "title": "Uganda IMAM Guidelines",
                "url": "https://platform.who.int/docs/UGA-CH-38-03-GUIDELINE-2016-eng-IMAM-Guidelines-for-Uganda-Jan-2016.pdf#page=88",
            }
        )
        == 2016
    )
    # Numbers inside a text-fragment anchor are not dates.
    assert _document_year({"title": "News", "url": "https://who.int/news/x#:~:text=1999%20and%202001"}) == 0
    assert _document_year({"title": "Untitled guidance", "url": "https://iris.who.int/bitstreams/abc/content"}) == 0


def test_candidate_order_prefers_the_current_edition_without_overriding_authority():
    from healthnavi.services.evidence_retrieval_adapter import _answer_candidates

    def guideline(title, url, score):
        return {
            "source": "crawl4ai",
            "title": title,
            "url": url,
            "journal_or_publisher": "Ministry of Health Uganda",
            "snippet": "Severe acute malnutrition treatment for children under five.",
            "evidence_type": "guideline",
            "final_score": score,
            "raw": {"retrieval_mode": "linked_pdf_text"},
        }

    items = [
        # Older edition retrieved with the better score.
        guideline("Uganda IMAM Guidelines", "https://platform.who.int/docs/UGA-GUIDELINE-2016-eng-IMAM-Jan-2016.pdf", 0.90),
        guideline("Uganda Clinical Guidelines", "https://www.differentiatedservicedelivery.org/uploads/UCG-2023-Final.pdf", 0.70),
        guideline("Consolidated guidance", "https://iris.who.int/bitstreams/undated/content", 0.80),
        {
            "source": "pubmed",
            "title": "Management of severe acute malnutrition: a 2026 review",
            "url": "https://pubmed.ncbi.nlm.nih.gov/99/",
            "journal_or_publisher": "Lancet",
            "year": 2026,
            "abstract": "Review of severe acute malnutrition treatment in children under five.",
            "evidence_type": "review",
            "final_score": 0.95,
        },
    ]

    ordered = _answer_candidates(
        items,
        query="treatment options for severe malnutrition in children under 5",
        source_preference_terms=("uganda",),
        deep_search=True,
    )

    titles = [item["title"] for item in ordered]
    # 2023 national guidance first, then undated guidance, then the 2016 edition.
    assert titles[:3] == ["Uganda Clinical Guidelines", "Consolidated guidance", "Uganda IMAM Guidelines"]
    # A very recent journal review still ranks below guideline-tier sources.
    assert titles[3].startswith("Management of severe acute malnutrition")


def test_curated_catalog_domains_outrank_article_databases():
    from healthnavi.evidence_retrieval.services.evidence_policy import (
        crawl_catalog_domains,
        source_trust_tier,
    )

    # The catalog is the curated list of sources the crawler is allowed to visit,
    # so every one of its domains must be at least primary-clinical tier. Before
    # this, the host of the current Uganda Clinical Guidelines PDF scored below PubMed.
    assert crawl_catalog_domains()
    for domain in crawl_catalog_domains():
        assert source_trust_tier("crawl4ai", f"https://{domain}/document.pdf") <= 3

    assert source_trust_tier("crawl4ai", "https://www.differentiatedservicedelivery.org/uploads/UCG-2023.pdf") == 1
    assert source_trust_tier("crawl4ai", "https://library.health.go.ug/x") == 0
    assert source_trust_tier("pubmed", "https://pubmed.ncbi.nlm.nih.gov/123/") == 3
    assert source_trust_tier("crawl4ai", "https://unlisted-blog.example.com/post") == 9


def test_clinical_specificity_separates_actionable_passages_from_pathway_prose():
    from healthnavi.evidence_retrieval.services.clinical_specificity import (
        clinical_specificity_score,
    )

    pathway_prose = (
        "Inpatient Therapeutic Care involves medical and nutritional therapy with "
        "psychosocial support, and has a stabilization phase and a rehabilitation phase."
    )
    actionable = (
        "Give F-75 at 130 ml/kg/day in 8 feeds and amoxicillin 40 mg/kg every 12 hours "
        "for 5 days, then transition to RUTF."
    )
    mechanism = (
        "Dolutegravir inhibits the integrase enzyme and prevents insertion of viral DNA "
        "into the host genome."
    )

    assert clinical_specificity_score(pathway_prose) == 0.0
    assert clinical_specificity_score(actionable) >= 0.6
    # Inert for qualitative questions: no candidate scores, so nothing is reordered.
    assert clinical_specificity_score(mechanism) == 0.0
    assert clinical_specificity_score("") == 0.0


def test_specificity_breaks_ties_without_overriding_source_authority():
    from healthnavi.services.evidence_retrieval_adapter import _answer_candidates

    def passage(title, url, snippet, score):
        return {
            "source": "crawl4ai",
            "title": title,
            "url": url,
            "journal_or_publisher": "Ministry of Health Uganda",
            "snippet": snippet,
            "evidence_type": "guideline",
            "final_score": score,
            "raw": {"retrieval_mode": "linked_pdf_text"},
        }

    items = [
        passage(
            "National guideline",
            "https://library.health.go.ug/g.pdf#page=59",
            "Severe acute malnutrition is managed through an outpatient therapeutic programme "
            "offering home-based treatment and rehabilitation.",
            0.90,
        ),
        passage(
            "National guideline",
            "https://library.health.go.ug/g.pdf#page=73",
            "For severe acute malnutrition give amoxicillin 40 mg/kg every 12 hours for 5 days "
            "with RUTF providing 150 kcal/kg/day.",
            0.60,
        ),
        {
            "source": "pubmed",
            "title": "Trial of therapeutic feeds",
            "url": "https://pubmed.ncbi.nlm.nih.gov/7/",
            "journal_or_publisher": "Lancet",
            "year": 2025,
            "abstract": "Severe acute malnutrition treated with 100 ml/kg/day of F-100 every 4 hours for 7 days.",
            "evidence_type": "clinical_trial",
            "final_score": 0.99,
        },
    ]

    ordered = _answer_candidates(
        items,
        query="treatment for severe acute malnutrition",
        source_preference_terms=(),
        deep_search=True,
    )

    # Within the guideline, the dosing page outranks its pathway page despite the
    # lower retrieval score.
    guideline_pages = [
        item["url"].rsplit("#", 1)[-1] for item in ordered if item["source"] == "crawl4ai"
    ]
    assert guideline_pages == ["page=73", "page=59"]
    # The journal article never precedes the guideline it competes with.
    assert ordered[0]["source"] == "crawl4ai"


def test_candidates_take_the_best_passage_of_each_document_before_a_second_from_any():
    from healthnavi.services.evidence_retrieval_adapter import _answer_candidates

    def passage(doc, page, snippet, score):
        return {
            "source": "crawl4ai",
            "title": f"Uganda guideline on acute malnutrition, volume {doc}",
            "url": f"https://library.health.go.ug/{doc}.pdf#page={page}",
            "journal_or_publisher": "Ministry of Health Uganda",
            "snippet": snippet,
            "evidence_type": "guideline",
            "final_score": score,
            "raw": {"retrieval_mode": "linked_pdf_text"},
        }

    items = [
        passage("a", 10, "Give amoxicillin 40 mg/kg every 12 hours for 5 days in malnutrition.", 0.95),
        passage("a", 11, "Give amoxicillin 40 mg/kg twice daily for 5 days in acute malnutrition.", 0.94),
        passage("a", 12, "Amoxicillin dosing 40 mg/kg every 12 hours continues for 5 days.", 0.93),
        passage("b", 3, "Admit malnutrition with complications, treat as outpatient when appetite is intact.", 0.50),
    ]

    candidates = _answer_candidates(
        items,
        query="treatment of acute malnutrition in children",
        source_preference_terms=(),
        deep_search=False,
    )

    # Breadth before depth: the second document appears before the first document's
    # second page, so a long guideline cannot spend every slot on one viewpoint.
    assert candidates[0]["url"].endswith("a.pdf#page=10")
    assert candidates[1]["url"].endswith("b.pdf#page=3")


def test_second_passage_from_a_document_is_the_complementary_one():
    from healthnavi.services.evidence_retrieval_adapter import _answer_candidates

    def passage(page, snippet, score):
        return {
            "source": "crawl4ai",
            "title": "National guideline on severe acute malnutrition",
            "url": f"https://library.health.go.ug/g.pdf#page={page}",
            "journal_or_publisher": "Ministry of Health Uganda",
            "snippet": snippet,
            "evidence_type": "guideline",
            "final_score": score,
            "raw": {"retrieval_mode": "linked_pdf_text"},
        }

    items = [
        passage(91, "Transition from F-75 to RUTF over 2-3 days at 100-135 kcal/kg/day.", 0.95),
        passage(92, "Continue RUTF at 100-135 kcal/kg/day, topping up with F-75 over 2-3 days.", 0.94),
        passage(59, "Decide the malnutrition pathway: complicated cases are admitted, uncomplicated cases with appetite are treated at home.", 0.60),
    ]

    candidates = _answer_candidates(
        items,
        query="treatment of severe acute malnutrition",
        source_preference_terms=(),
        deep_search=False,
    )

    pages = [item["url"].rsplit("=", 1)[-1] for item in candidates]
    # Page 92 repeats page 91; the triage page adds something, so it is taken first
    # even though it scored lower in retrieval.
    assert pages[:2] == ["91", "59"]


def test_contentless_passages_do_not_take_candidate_slots():
    from healthnavi.services.evidence_retrieval_adapter import _answer_candidates

    def passage(page, snippet):
        return {
            "source": "crawl4ai",
            "title": "National malnutrition guideline",
            "url": f"https://library.health.go.ug/g.pdf#page={page}",
            "journal_or_publisher": "Ministry of Health Uganda",
            "snippet": snippet,
            "evidence_type": "guideline",
            "final_score": 0.9 - page / 1000,
            "raw": {"retrieval_mode": "linked_pdf_text"},
        }

    items = [
        passage(3, "Management of Severe Acute Malnutrition in children: working towards results at scale"),
        passage(65, "Per DALY $26 -- $42 $53 - Per life-year saved - - - $125 (119-152) Source: Sadler et al."),
        passage(
            91,
            "Do not give IV fluids routinely in severe acute malnutrition. IV fluids can cause fluid "
            "overload and heart failure in a severely malnourished child, so use ReSoMal orally instead.",
        ),
    ]

    candidates = _answer_candidates(
        items,
        query="treatment of severe acute malnutrition in children",
        source_preference_terms=(),
        deep_search=False,
    )

    # A cover page and a cost table match the query lexically but say nothing clinical.
    assert [item["url"].rsplit("=", 1)[-1] for item in candidates] == ["91"]


def test_contentless_filter_never_empties_the_candidate_set():
    from healthnavi.services.evidence_retrieval_adapter import _answer_candidates

    thin_only = [
        {
            "source": "crawl4ai",
            "title": "Malnutrition guideline cover",
            "url": "https://library.health.go.ug/g.pdf#page=1",
            "journal_or_publisher": "Ministry of Health Uganda",
            "snippet": "Severe acute malnutrition guideline",
            "evidence_type": "guideline",
            "final_score": 0.9,
            "raw": {"retrieval_mode": "static_html"},
        }
    ]

    # Better a thin source than none: the filter is a preference, not a hard gate.
    assert _answer_candidates(
        thin_only,
        query="severe acute malnutrition treatment",
        source_preference_terms=(),
        deep_search=False,
    ) == thin_only
