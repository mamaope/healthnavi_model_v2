import asyncio
import time

from healthnavi.evidence_retrieval.config import EvidenceRetrievalSettings, get_settings
from healthnavi.evidence_retrieval.models import EvidenceItem, EvidenceSource
from healthnavi.evidence_retrieval.providers import crawl4ai_provider as crawl_provider_module
from healthnavi.evidence_retrieval.providers.crawl4ai_provider import (
    Crawl4AIProvider,
    CrawlSource,
    _best_snippet,
    _read_static_cache,
    _source_selection_terms,
    _write_static_cache,
)
from healthnavi.evidence_retrieval.providers.official_health_api_provider import (
    _query_tokens as _official_health_api_query_tokens,
)
from healthnavi.evidence_retrieval.services.evidence_ranker import rank_evidence_items
from healthnavi.evidence_retrieval.services.query_builder import (
    build_provider_query,
    build_query_plan,
)
from healthnavi.evidence_retrieval.services.evidence_policy import (
    evidence_policy_sort_key,
)
from healthnavi.evidence_retrieval.services.evidence_search_service import EvidenceSearchService
from healthnavi.services.evidence_retrieval_adapter import (
    _active_source_preference_terms,
    _answer_looks_like_service_status,
    _answer_top_k,
    _citations_for_answer,
    _citations_from_evidence,
    _ensure_reference_urls,
    _evidence_country_code_for_search,
    _evidence_context_for_prompt,
    _filter_evidence_items,
    _include_global_evidence_when_helpful,
    _local_followup_questions,
    _local_evidence_provider_mode,
    _model_timeout_for_mode,
    _normalize_model_service_response,
    _retrieval_planner_enabled,
    _retrieval_queries_for_request,
    _sanitize_answer_style,
    _search_settings_for_mode,
    _select_answer_evidence,
    _source_preference_terms,
    generate_model_service_response,
)


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
        (1, 0),
        (1, 0),
        (1, 0),
        (3, 2),
        (4, 6),
    ]


def test_crawl_source_selection_prefers_topic_specific_sources_without_local_default():
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

    tb_sources = [source.name for source in provider._select_sources("tuberculosis treatment regimen")]
    nutrition_sources = [
        source.name
        for source in provider._select_sources("severe malnutrition children treatment")
    ]

    assert tb_sources[0] == "WHO Tuberculosis Treatment Guidance"
    assert "WHO HIV Updated Recommendations - NCBI Bookshelf" not in tb_sources
    assert nutrition_sources[0] == "UNICEF Nutrition Guidance"
    assert "Uganda Integrated Management of Acute Malnutrition Guidelines" in nutrition_sources


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

    sources = [
        source.name
        for source in provider._select_sources(
            "ceftriaxone severe pneumonia adult drug monograph prescribing information dosage dose route frequency"
        )
    ]

    assert sources[:2] == ["MSF Essential Drugs", "DailyMed Drug Labels"]
    assert "European Society of Cardiology Guidelines" not in sources


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

    sources = [
        source.name
        for source in provider._select_sources(
            "treatment options severe malnutrition 5 child clinical guideline recommendation"
        )
    ]

    assert "Uganda Integrated Management of Acute Malnutrition Guidelines" in sources
    assert any(source in sources for source in ["UNICEF Nutrition Guidance", "World Health Organization"])


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
    assert "thiazide-like diuretic" in str(item.snippet)
    assert "ACE inhibitor or ARB" in str(item.snippet)


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


def test_answer_formatting_adds_paragraphs_and_repairs_spacing_artifacts():
    answer = (
        "Treatment options for severe malnutrition in children under 5 years include nutritional "
        "supplementation with Ready-to-Use Supplementary Food (RUSF) orReady-to-Use Therapeutic "
        "Food (RUTF), particularly for children after discharge[1]. Vitamin A supplementation is "
        "also part of treatment for children with severe acute malnutrition[2]. The WHO Pocket "
        "book provides guidance consistent with Integrated Managementof Childhood Illness "
        "guidelines[3]. Children with danger signs need urgent assessment and stabilization[1]."
    )
    citations = [
        {
            "title": "5.4 Treatment of complicated cases | MSF Medical Guidelines",
            "url": "https://medicalguidelines.msf.org/en/viewport/mme/english/5-4-treatment-of-complicated-cases-32408073.html",
            "source_label": "Guideline Page",
            "year": None,
        },
        {
            "title": "Guideline: updates on the management of severe acute malnutrition in infants andchildren",
            "url": "https://www.who.int/publications-detail-redirect/9789241506328",
            "source_label": "",
            "year": None,
        },
        {
            "title": "WHO Pocket book of hospital care forchildren",
            "url": "https://pmnch.who.int/resources/publications/m/item/who-pocket-book-of-hospital-care-for-children",
            "source_label": "",
            "year": None,
        },
    ]

    rendered = _ensure_reference_urls(answer, citations)

    assert "or Ready-to-Use" in rendered
    assert "Integrated Management of Childhood Illness" in rendered
    assert "for children" in rendered
    assert "\n\nVitamin A supplementation" in rendered
    assert (
        "[1](https://medicalguidelines.msf.org/en/viewport/mme/english/"
        "5-4-treatment-of-complicated-cases-32408073.html)"
    ) in rendered
    assert "[[1]](" not in rendered
    assert "1. [Treatment of complicated cases" in rendered
    assert "1. [5.4 Treatment" not in rendered
    assert "Guideline Page, n.d." not in rendered


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


def test_evidence_country_hint_defaults_to_open_search(monkeypatch):
    monkeypatch.delenv("EMPIRICO_EVIDENCE_COUNTRY_CODE", raising=False)
    monkeypatch.delenv("EMPIRICO_MODEL_SERVICE_COUNTRY_CODE", raising=False)

    assert _evidence_country_code_for_search() is None


def test_evidence_country_hint_can_be_global(monkeypatch):
    monkeypatch.setenv("EMPIRICO_EVIDENCE_COUNTRY_CODE", "global")

    assert _evidence_country_code_for_search() == "GLOBAL"


def test_legacy_country_hint_is_still_honored(monkeypatch):
    monkeypatch.delenv("EMPIRICO_EVIDENCE_COUNTRY_CODE", raising=False)
    monkeypatch.setenv("EMPIRICO_MODEL_SERVICE_COUNTRY_CODE", "ug")

    assert _evidence_country_code_for_search() == "UG"


def test_local_evidence_provider_mode_defaults_to_web(monkeypatch):
    monkeypatch.delenv("EMPIRICO_EVIDENCE_PROVIDER_MODE", raising=False)

    assert _local_evidence_provider_mode() == "web"


def test_local_evidence_provider_mode_honors_crawl_alias(monkeypatch):
    monkeypatch.setenv("EMPIRICO_EVIDENCE_PROVIDER_MODE", "crawl")

    assert _local_evidence_provider_mode() == "crawl"


def test_source_preference_terms_are_configurable(monkeypatch):
    monkeypatch.setenv("EMPIRICO_SOURCE_PREFERENCE_TERMS", "health.go.ug; WHO AFRO\nAfrica")

    assert _source_preference_terms() == ("health.go.ug", "who afro", "africa")


def test_default_source_preference_terms_are_empty(monkeypatch):
    monkeypatch.delenv("EMPIRICO_SOURCE_PREFERENCE_TERMS", raising=False)

    assert _source_preference_terms() == ()


def test_configured_source_preferences_activate_only_when_context_matches():
    terms = ("uganda", "health.go.ug", "who afro", "africa")

    assert _active_source_preference_terms(
        "first-line treatment for stage 1 hypertension",
        terms,
    ) == ()
    assert _active_source_preference_terms(
        "HIV treatment guideline Uganda",
        terms,
    ) == terms


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
        "adult HIV treatment Kampala",
        "HIV antiretroviral therapy guideline Uganda",
        "30 year old female in Kampala has HIV, what is the treatment for her?",
    )


def test_quick_response_uses_single_local_retrieval_query(monkeypatch):
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
        assert payload["max_output_tokens"] == 900
        return {
            "answer": "Use a thiazide/thiazide-like diuretic, ACE inhibitor or ARB, or long-acting dihydropyridine CCB when medication is indicated [1].",
            "diagnosis_complete": True,
        }

    monkeypatch.setenv("EMPIRICO_FOLLOWUP_MODE", "off")
    monkeypatch.setenv("EMPIRICO_QUICK_MODEL_NAME", "gemini-2.5-flash-lite")
    monkeypatch.setenv("EMPIRICO_QUICK_MAX_OUTPUT_TOKENS", "900")
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
    assert retrieval_calls[0]["top_k"] == 6
    assert retrieval_calls[0]["deep_search"] is False
    assert "[1](https://iris.who.int/example)" in answer
    assert complete is True
    assert prompt_type == "empirico_quick_search"
    assert followups == []


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


def test_deep_broadens_retrieval_while_quick_uses_original_query(monkeypatch):
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

    assert quick_queries == (question,)
    assert deep_queries == (
        "standard initial treatment guideline",
        "adult treatment regimen",
        "practical dosing details",
        question,
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

    assert not _retrieval_planner_enabled(False)

    monkeypatch.setenv("EMPIRICO_DEEP_ENABLE_RETRIEVAL_PLANNER", "auto")

    assert _retrieval_planner_enabled(True)

    monkeypatch.setenv("EMPIRICO_DEEP_ENABLE_RETRIEVAL_PLANNER", "true")

    assert _retrieval_planner_enabled(True)

    monkeypatch.setenv("EMPIRICO_QUICK_ENABLE_RETRIEVAL_PLANNER", "false")

    assert not _retrieval_planner_enabled(False)


def test_semantic_evidence_selector_uses_model_source_numbers(monkeypatch):
    async def fake_post_model_response(payload, timeout_seconds):
        assert payload["prompt_type"] == "empirico_evidence_source_selection"
        assert "Return only valid JSON" in payload["prompt"]
        assert "Retrieved sources:" in payload["prompt"]
        return {"answer": '{"source_numbers":[2]}'}

    monkeypatch.setenv("EMPIRICO_ENABLE_SEMANTIC_EVIDENCE_SELECTION", "true")
    monkeypatch.setattr(
        "healthnavi.services.evidence_retrieval_adapter._post_model_response",
        fake_post_model_response,
    )
    evidence = [
        {
            "source": "crawl4ai",
            "title": "Tangential implementation report",
            "url": "https://example.org/report",
            "snippet": "Implementation background without treatment details.",
            "evidence_type": "guideline",
        },
        {
            "source": "crawl4ai",
            "title": "Direct first-line treatment guideline",
            "url": "https://www.who.int/publications/example",
            "snippet": "First-line treatment uses the preferred regimen and alternatives.",
            "evidence_type": "guideline",
        },
    ]

    selected = asyncio.run(
        _select_answer_evidence(
            query="What is the first-line treatment?",
            patient_data="",
            chat_history="",
            evidence=evidence,
            deep_search=False,
            answer_top_k=4,
        )
    )

    assert selected[0] == evidence[1]
    assert selected[1:] == [evidence[0]]


def test_quick_mode_uses_bounded_retrieval_settings(monkeypatch):
    monkeypatch.setenv("EMPIRICO_QUICK_SEARCH_TOP_K", "9")
    monkeypatch.setenv("EMPIRICO_QUICK_ANSWER_TOP_K", "3")
    monkeypatch.setenv("EMPIRICO_QUICK_RETRIEVAL_TIME_BUDGET_SECONDS", "12.25")
    monkeypatch.setenv("EMPIRICO_QUICK_CRAWL_TIME_BUDGET_SECONDS", "10.25")
    monkeypatch.setenv("EMPIRICO_QUICK_REQUEST_TIMEOUT_SECONDS", "12")
    monkeypatch.setenv("EMPIRICO_QUICK_CRAWL_MAX_SOURCES", "6")
    monkeypatch.setenv("EMPIRICO_QUICK_CRAWL_MAX_PAGES", "8")
    monkeypatch.setenv("EMPIRICO_QUICK_MAX_RESULTS_PER_PROVIDER", "5")
    get_settings.cache_clear()

    settings = _search_settings_for_mode(False)
    get_settings.cache_clear()

    assert settings.retrieval_time_budget_seconds == 12.25
    assert settings.crawl_time_budget_seconds == 10.25
    assert settings.request_timeout_seconds == 12
    assert settings.crawl_max_sources == 6
    assert settings.crawl_max_pages == 8
    assert settings.max_results_per_provider == 5
    assert _answer_top_k(False) == 6


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
    get_settings.cache_clear()

    settings = _search_settings_for_mode(False)
    get_settings.cache_clear()

    assert settings.retrieval_time_budget_seconds == 16
    assert settings.crawl_time_budget_seconds == 14
    assert settings.request_timeout_seconds == 20
    assert settings.crawl_max_sources == 8
    assert settings.crawl_max_pages == 14


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
    assert settings.crawl_max_sources == 6
    assert settings.crawl_max_pages == 8
    assert settings.max_results_per_provider == 6


def test_retrieval_defaults_allow_web_crawl_to_finish():
    settings = EvidenceRetrievalSettings()

    assert settings.retrieval_time_budget_seconds == 18
    assert settings.crawl_time_budget_seconds == 14


def test_model_timeout_uses_global_timeout_when_mode_override_absent(monkeypatch):
    monkeypatch.setenv("EMPIRICO_QUICK_MODEL_TIMEOUT_SECONDS", "")
    monkeypatch.setenv("EMPIRICO_DEEP_MODEL_TIMEOUT_SECONDS", "")
    monkeypatch.setenv("MODEL_SERVICE_TIMEOUT_SECONDS", "180")

    assert _model_timeout_for_mode(False) == 180
    assert _model_timeout_for_mode(True) == 180


def test_model_timeout_mode_override_is_capped_by_global_timeout(monkeypatch):
    monkeypatch.setenv("MODEL_SERVICE_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("EMPIRICO_QUICK_MODEL_TIMEOUT_SECONDS", "60")

    assert _model_timeout_for_mode(False) == 45


def test_model_timeout_ignores_stale_tiny_mode_overrides(monkeypatch):
    monkeypatch.setenv("MODEL_SERVICE_TIMEOUT_SECONDS", "180")
    monkeypatch.setenv("EMPIRICO_QUICK_MODEL_TIMEOUT_SECONDS", "4.7")
    monkeypatch.setenv("EMPIRICO_DEEP_MODEL_TIMEOUT_SECONDS", "8")

    assert _model_timeout_for_mode(False) == 180
    assert _model_timeout_for_mode(True) == 180


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


def test_sanitize_answer_style_removes_provided_evidence_phrasing():
    answer = (
        "Based on the provided evidence, The provided evidence supports thiazide "
        "diuretics as one first-line option [1]."
    )

    cleaned = _sanitize_answer_style(answer)

    assert "provided evidence" not in cleaned.lower()
    assert "cited source" not in cleaned.lower()
    assert cleaned.startswith("Thiazide diuretics")


def test_sanitize_answer_style_removes_appendix_and_current_evidence_phrasing():
    answer = (
        "The cited sources indicates that ceftriaxone is used for severe pneumonia [1]. "
        "However, the specific dosage is notdetailed within the provided text and refers "
        "to Appendix 13, which is not available in the current evidence [1]."
    )

    cleaned = _sanitize_answer_style(answer)

    assert cleaned.startswith("Ceftriaxone")
    assert "cited source" not in cleaned.lower()
    assert "provided text" not in cleaned.lower()
    assert "current evidence" not in cleaned.lower()
    assert "appendix 13" not in cleaned.lower()
    assert "notdetailed" not in cleaned.lower()


def test_sanitize_answer_style_removes_empty_source_disclaimer():
    answer = (
        "The cited sources does not specify a single first-line medication. "
        "It indicates that initial therapy can use thiazide diuretics, ACE inhibitors, "
        "ARBs, or long-acting calcium-channel blockers [1]."
    )

    cleaned = _sanitize_answer_style(answer)

    assert cleaned.startswith("Initial therapy can use")
    assert "cited source" not in cleaned.lower()
    assert "does not specify" not in cleaned.lower()


def test_sanitize_answer_style_removes_provided_information_disclaimer():
    answer = (
        "The provided information does not specify whether she is pregnant. "
        "DTG-based antiretroviral therapy is the preferred first-line approach [1]."
    )

    cleaned = _sanitize_answer_style(answer)

    assert cleaned == "DTG-based antiretroviral therapy is the preferred first-line approach [1]."
    assert "provided information" not in cleaned.lower()
    assert "does not specify" not in cleaned.lower()


def test_sanitize_answer_style_removes_source_name_attribution():
    answer = (
        "For adults with hypertension requiring pharmacological treatment, "
        "the World Health Organization (WHO) recommends using thiazide-like agents [1]."
    )

    cleaned = _sanitize_answer_style(answer)

    assert "World Health Organization" not in cleaned
    assert "WHO recommends" not in cleaned
    assert cleaned.startswith("For adults with hypertension requiring pharmacological treatment, use")

    direct_object = _sanitize_answer_style(
        "For a 30-year-old female with HIV, the World Health Organization (WHO) "
        "recommends a dolutegravir-based regimen as first-line ART [1]."
    )
    assert "World Health Organization" not in direct_object
    assert "WHO" not in direct_object
    assert direct_object.startswith("For a 30-year-old female with HIV, a dolutegravir-based")

    initiating = _sanitize_answer_style(
        "For adults with hypertension requiring pharmacological treatment, "
        "the World Health Organization (WHO) recommends initiating treatment "
        "with thiazide-like agents [1]."
    )
    assert "World Health Organization" not in initiating
    assert "WHO" not in initiating
    assert initiating.startswith("For adults with hypertension requiring pharmacological treatment, initiate")


def test_sanitize_answer_style_removes_source_name_support_sentence():
    answer = (
        "Use TDF + 3TC + DTG as preferred first-line ART for adults [1]. "
        "The World Health Organization (WHO) has consistently supported the adoption "
        "of DTG as a preferred option in first- and second-line ART [1]."
    )

    cleaned = _sanitize_answer_style(answer)

    assert "World Health Organization" not in cleaned
    assert "supported the adoption" not in cleaned
    assert cleaned == "Use TDF + 3TC + DTG as preferred first-line ART for adults [1]."


def test_service_status_answers_are_not_treated_as_medical_answers():
    assert _answer_looks_like_service_status(
        "The model service is temporarily busy. Please try again."
    )
    assert not _answer_looks_like_service_status(
        "Start antiretroviral therapy promptly after confirming HIV diagnosis."
    )


def test_reference_urls_are_rebuilt_and_inline_markers_linked():
    answer = (
        "Immediate ART is generally recommended after diagnosis [1, 2].\n\n"
        "**References**\n"
        "- old model reference"
    )
    citations = [
        {
            "title": "Adult HIV guideline",
            "url": "https://example.org/hiv",
            "source_label": "Guideline Page",
            "year": 2025,
        },
        {
            "title": "ART review",
            "url": "https://example.org/art-review",
            "source_label": "PubMed",
            "year": 2024,
        },
    ]

    rendered = _ensure_reference_urls(answer, citations)

    assert (
        "Immediate ART is generally recommended after diagnosis "
        "[1](https://example.org/hiv) [2](https://example.org/art-review)."
    ) in rendered
    assert "[[1]](" not in rendered
    assert "old model reference" not in rendered
    assert "1. [Adult HIV guideline](https://example.org/hiv) - Guideline Page, 2025 - https://example.org/hiv" in rendered
    assert "2. [ART review](https://example.org/art-review) - PubMed, 2024 - https://example.org/art-review" in rendered


def test_reference_urls_rewrite_model_supplied_inline_links():
    answer = "Use DTG-based ART as first-line treatment [2](https://untrusted.example/source)."
    citations = [
        {
            "title": "Background source",
            "url": "https://example.org/background",
            "source_label": "PubMed",
            "year": 2022,
        },
        {
            "title": "HIV treatment guideline",
            "url": "https://example.org/hiv-guideline",
            "source_label": "Guideline Page",
            "year": 2025,
        },
    ]

    rendered = _ensure_reference_urls(answer, citations)

    assert "https://untrusted.example/source" not in rendered
    assert "Use DTG-based ART as first-line treatment [1](https://example.org/hiv-guideline)." in rendered
    assert "Background source" not in rendered
    assert "1. [HIV treatment guideline](https://example.org/hiv-guideline)" in rendered


def test_reference_urls_omit_placeholder_metadata_when_missing():
    answer = "Use IPTp in eligible malaria-endemic pregnancy settings [1]."
    citations = [
        {
            "title": "Intermittent preventive treatment to reduce malaria risk",
            "url": "https://www.who.int/tools/elena/interventions/iptp-pregnancy",
            "source_label": "Guideline Page",
            "year": None,
        },
    ]

    rendered = _ensure_reference_urls(answer, citations)

    assert (
        "Use IPTp in eligible malaria-endemic pregnancy settings "
        "[1](https://www.who.int/tools/elena/interventions/iptp-pregnancy)."
    ) in rendered
    assert "[[1]](" not in rendered
    assert "Guideline Page, n.d." not in rendered
    assert (
        "1. [Intermittent preventive treatment to reduce malaria risk]"
        "(https://www.who.int/tools/elena/interventions/iptp-pregnancy)"
        " - https://www.who.int/tools/elena/interventions/iptp-pregnancy"
    ) in rendered


def test_reference_urls_compact_to_only_cited_sources():
    answer = "Use intravenous artesunate for severe malaria in pregnancy [3]."
    citations = [
        {
            "title": "Background article",
            "url": "https://example.org/background",
            "source_label": "Semantic Scholar",
            "year": 2022,
        },
        {
            "title": "General malaria review",
            "url": "https://example.org/review",
            "source_label": "PubMed",
            "year": 2023,
        },
        {
            "title": "Severe malaria pregnancy review",
            "url": "https://example.org/severe-malaria-pregnancy",
            "source_label": "Semantic Scholar",
            "year": 2025,
        },
    ]

    rendered = _ensure_reference_urls(answer, citations)

    assert (
        "Use intravenous artesunate for severe malaria in pregnancy "
        "[1](https://example.org/severe-malaria-pregnancy)."
    ) in rendered
    assert "[[1]](" not in rendered
    assert "[3]" not in rendered
    assert "Background article" not in rendered
    assert "General malaria review" not in rendered
    assert "1. [Severe malaria pregnancy review](https://example.org/severe-malaria-pregnancy)" in rendered


def test_citations_follow_nested_v3_reference_fields(monkeypatch):
    monkeypatch.setenv("MODEL_SERVICE_BASE_URL", "https://model.empirico.ai")
    item = {
        "source": "crawl4ai",
        "raw": {
            "document_title": "Uganda Clinical Guidelines 2023",
            "public_source_url": "/v1/references/uganda_clinical_guidelines_2023:0042:abc123",
            "page_start": 42,
            "section_title": "Nutrition | Severe acute malnutrition",
            "publisher": "Ministry of Health Uganda",
            "publication_year": 2023,
        },
        "snippet": "Treatment includes stabilization and therapeutic feeding.",
        "evidence_type": "guideline",
    }

    citations = _citations_from_evidence([item])
    context = _evidence_context_for_prompt([item])

    assert citations[0]["url"] == (
        "https://model.empirico.ai/v1/references/"
        "uganda_clinical_guidelines_2023:0042:abc123#page=42"
    )
    assert "Uganda Clinical Guidelines 2023, p. 42" in str(citations[0]["title"])
    assert "Severe acute malnutrition" in str(citations[0]["title"])
    assert citations[0]["source_label"] == "Ministry of Health Uganda"
    assert citations[0]["year"] == 2023
    assert "Source: Ministry of Health Uganda; Year: 2023; URL:" in context


def test_quick_evidence_context_keeps_treatment_intent_sentences():
    item = {
        "source": "crawl4ai",
        "title": "Update of recommendations on first- and second-line antiretroviral regimens",
        "url": "https://www.who.int/publications/i/item/WHO-CDS-HIV-19.15",
        "snippet": (
            "Number of pages 15. Reference numbers WHO/CDS/HIV/19.15. "
            "The updated recommendations support dolutegravir as the preferred "
            "antiretroviral drug in first- and second-line regimens for people with HIV."
        ),
        "evidence_type": "clinical_resource",
    }

    context = _evidence_context_for_prompt(
        [item],
        deep_search=False,
        query="30 year old female in Kampala has HIV, what is the treatment?",
    )

    assert "dolutegravir" in context
    assert "preferred antiretroviral drug" in context


def test_model_service_references_join_when_answer_cites_beyond_local_sources(monkeypatch):
    monkeypatch.setenv("MODEL_SERVICE_BASE_URL", "https://model.empirico.ai")
    answer = "Use the signed model-service reference for the exact source [2]."
    local_citations = [
        {
            "title": "Local web source",
            "url": "https://www.who.int/example",
            "source_label": "WHO",
            "year": 2024,
        }
    ]
    model_data = {
        "references": [
            {
                "citation_label": "HealthNavy knowledge base source",
                "signed_reference_url": "/v1/references/kb:0007:abc123",
                "page_start": 7,
                "source_label": "HealthNavy KB",
                "year": 2025,
            }
        ]
    }

    citations = _citations_for_answer(answer, local_citations, model_data)
    rendered = _ensure_reference_urls(answer, citations)

    assert (
        "Use the signed model-service reference for the exact source "
        "[1](https://model.empirico.ai/v1/references/kb:0007:abc123#page=7)."
    ) in rendered
    assert "[[1]](" not in rendered
    assert "Local web source" not in rendered
    assert "knowledge base source" in rendered
    assert "HealthNavy KB, 2025" in rendered


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


def test_global_evidence_can_join_uganda_preferred_results_for_generic_queries(monkeypatch):
    monkeypatch.setenv("EMPIRICO_EVIDENCE_PROVIDER_MODE", "web")
    preference_terms = ("uganda", "health.go.ug", "africa")
    local_items = [
        {
            "source": "crawl4ai",
            "title": "Uganda hypertension guidance",
            "url": "https://health.go.ug/hypertension",
            "snippet": "Uganda guidance for hypertension.",
            "evidence_type": "guideline",
            "raw": {"retrieval_mode": "static_html"},
        },
        {
            "source": "semantic_scholar",
            "title": "Africa hypertension review",
            "url": "https://www.semanticscholar.org/paper/africa-hypertension",
            "abstract": "Hypertension evidence from African settings.",
            "evidence_type": "review",
        },
        {
            "source": "crawl4ai",
            "title": "Uganda cardiovascular care",
            "url": "https://health.go.ug/cardiovascular",
            "snippet": "Uganda cardiovascular care information.",
            "evidence_type": "guideline",
            "raw": {"retrieval_mode": "static_html"},
        },
    ]
    global_item = {
        "source": "crawl4ai",
        "title": "WHO hypertension guideline",
        "url": "https://www.who.int/publications/example-hypertension",
        "snippet": "Global WHO hypertension guideline recommendations.",
        "evidence_type": "guideline",
        "raw": {"retrieval_mode": "static_html"},
    }

    blended = _include_global_evidence_when_helpful(
        query="first-line treatment for stage 1 hypertension",
        evidence=local_items,
        raw_evidence=[*local_items, global_item],
        source_preference_terms=preference_terms,
        answer_top_k=3,
    )

    assert [item["title"] for item in blended] == [
        "Uganda hypertension guidance",
        "Africa hypertension review",
        "WHO hypertension guideline",
    ]


def test_global_evidence_does_not_replace_strong_explicit_uganda_results(monkeypatch):
    monkeypatch.setenv("EMPIRICO_EVIDENCE_PROVIDER_MODE", "web")
    preference_terms = ("uganda", "health.go.ug", "africa")
    local_items = [
        {
            "source": "crawl4ai",
            "title": "Uganda malaria guideline",
            "url": "https://health.go.ug/malaria",
            "snippet": "Uganda malaria treatment guidance.",
            "evidence_type": "guideline",
            "raw": {"retrieval_mode": "static_html"},
        },
        {
            "source": "crawl4ai",
            "title": "Uganda malaria pregnancy guide",
            "url": "https://health.go.ug/malaria-pregnancy",
            "snippet": "Uganda severe malaria pregnancy guidance.",
            "evidence_type": "guideline",
            "raw": {"retrieval_mode": "static_html"},
        },
        {
            "source": "semantic_scholar",
            "title": "Africa severe malaria in pregnancy review",
            "url": "https://www.semanticscholar.org/paper/africa-malaria-pregnancy",
            "abstract": "African malaria-endemic settings.",
            "evidence_type": "review",
        },
    ]
    global_item = {
        "source": "crawl4ai",
        "title": "WHO malaria guideline",
        "url": "https://www.who.int/publications/example-malaria",
        "snippet": "Global WHO malaria treatment guidance.",
        "evidence_type": "guideline",
        "raw": {"retrieval_mode": "static_html"},
    }

    blended = _include_global_evidence_when_helpful(
        query="severe malaria in pregnancy treatment in Uganda",
        evidence=local_items,
        raw_evidence=[*local_items, global_item],
        source_preference_terms=preference_terms,
        answer_top_k=3,
    )

    assert blended == local_items
