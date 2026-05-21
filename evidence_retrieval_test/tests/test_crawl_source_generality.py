from evidence_retrieval_test.src.config import EvidenceRetrievalSettings
from evidence_retrieval_test.src.models import EvidenceItem
from evidence_retrieval_test.src.providers.base import BaseEvidenceProvider
from evidence_retrieval_test.src.providers.crawl4ai_provider import (
    Crawl4AIProvider,
    CrawlSource,
)
from evidence_retrieval_test.src.services.evidence_search_service import (
    EvidenceSearchService,
    _select_diverse_results,
)


def test_seed_targets_are_limited_to_broad_source_pages() -> None:
    source = CrawlSource(
        name="Example Clinical Library",
        publisher="Example Publisher",
        domains=("example.org",),
        topics=("clinical guidelines", "emergency care", "all diseases"),
        priority=1.0,
        seed_urls=(
            "https://example.org/guidelines",
            "https://example.org/conditions/example-condition/treatment.html",
        ),
        search_urls=("https://example.org/search?q={query}",),
    )
    provider = Crawl4AIProvider(
        EvidenceRetrievalSettings(crawl_allowed_domains=["example.org"]),
        sources=[source],
    )

    urls = [url for _, url in provider._scored_seed_urls("child injury care", source)]

    assert urls == ["https://example.org/guidelines"]


def test_pdf_seed_items_include_approved_broad_guideline_pdfs() -> None:
    source = CrawlSource(
        name="Uganda Clinical Guidelines",
        publisher="Ministry of Health Uganda",
        domains=("example.org",),
        topics=("uganda", "clinical guidelines", "standard treatment", "paediatrics"),
        priority=1.0,
        seed_urls=("https://example.org/Uganda-Clinical-Guidelines-2023.pdf",),
        search_urls=(),
    )
    provider = Crawl4AIProvider(
        EvidenceRetrievalSettings(crawl_allowed_domains=["example.org"]),
        sources=[source],
    )

    items = provider._pdf_seed_items("treatment of fever in a 2 year old child in Uganda", [source], 3)

    assert items
    assert items[0].title == "Uganda Clinical Guidelines 2023"
    assert items[0].evidence_type == "guideline"
    assert items[0].url == "https://example.org/Uganda-Clinical-Guidelines-2023.pdf"


def test_diverse_selection_requires_the_actual_query_topic() -> None:
    generic_treatment = EvidenceItem(
        id="crawl4ai:generic",
        source="crawl4ai",
        title="Clinical treatment guideline",
        snippet="Treatment recommendations for clinical care.",
        url="https://example.org/guidelines",
        evidence_type="guideline",
        relevance_score=0.3,
        final_score=0.4,
    )
    matching_topic = EvidenceItem(
        id="crawl4ai:matching",
        source="crawl4ai",
        title="Child injury clinical guidance",
        snippet="Emergency injury assessment, referral, and treatment guidance.",
        url="https://example.org/guidelines/injury",
        evidence_type="guideline",
        relevance_score=0.3,
        final_score=0.35,
    )

    selected = _select_diverse_results(
        "how can i treat a child injury",
        [generic_treatment, matching_topic],
        top_k=2,
    )

    assert selected == [matching_topic]


def test_diverse_selection_rejects_generic_overlap_from_typo_query() -> None:
    unrelated = EvidenceItem(
        id="pubmed:trauma",
        source="pubmed",
        title="The Capacity to Manage Orthopaedic Trauma",
        abstract="Hospital systems for trauma care in boys and girls.",
        url="https://pubmed.ncbi.nlm.nih.gov/1/",
        evidence_type="journal_article",
        relevance_score=0.3,
        final_score=0.5,
        raw={"query_used": "how to manage menstration in girls"},
    )
    corrected_match = EvidenceItem(
        id="pubmed:menstruation",
        source="pubmed",
        title="Menstruation management in adolescent girls",
        abstract="Guidance for menstrual hygiene and menstruation symptoms in girls.",
        url="https://pubmed.ncbi.nlm.nih.gov/2/",
        evidence_type="review",
        relevance_score=0.3,
        final_score=0.4,
        raw={"query_used": "how to manage menstruation in girls"},
    )

    selected = _select_diverse_results(
        "how to manage menstration in girls",
        [unrelated, corrected_match],
        top_k=2,
    )

    assert selected == [corrected_match]


def test_search_service_keeps_relevant_results_with_typo_in_non_content_word() -> None:
    service = EvidenceSearchService(
        EvidenceRetrievalSettings(),
        providers=[_StaticProvider(EvidenceRetrievalSettings())],
    )

    result = service.search("treament of malaria in 5 year old", top_k=1)

    assert result.items
    assert result.items[0].title == "Treatment of malaria in children"


class _StaticProvider(BaseEvidenceProvider):
    source_name = "pubmed"

    def search(self, query: str, max_results: int) -> list[EvidenceItem]:
        return [
            EvidenceItem(
                id="pubmed:malaria-treatment",
                source="pubmed",
                title="Treatment of malaria in children",
                abstract="Treatment guidance for malaria in children under 5 years old.",
                url="https://pubmed.ncbi.nlm.nih.gov/example/",
                evidence_type="guideline",
                relevance_score=0.3,
            )
        ]
