from evidence_retrieval_test.src.models import EvidenceItem
from evidence_retrieval_test.src.services.citation_formatter import (
    build_llm_context,
    format_citations,
    short_citation,
)


def test_format_citations_returns_frontend_ready_objects() -> None:
    item = EvidenceItem(
        id="pubmed:1",
        source="pubmed",
        title="HIV treatment guidelines",
        abstract="Antiretroviral therapy is recommended.",
        authors=["Jane Doe", "John Smith"],
        journal_or_publisher="Clinical Journal",
        year=2024,
        doi="10.1000/example",
        url="https://pubmed.ncbi.nlm.nih.gov/1/",
        evidence_type="guideline",
    )

    citations = format_citations([item])

    assert citations[0]["source_label"] == "PubMed"
    assert citations[0]["markdown_citation"] == "[1](https://pubmed.ncbi.nlm.nih.gov/1/)"
    assert citations[0]["short_citation"] == "Doe et al., Clinical Journal, 2024"
    assert "guideline-level" in citations[0]["why_relevant"]


def test_llm_context_uses_numbered_citations() -> None:
    item = EvidenceItem(
        id="guideline:1",
        source="crawl4ai",
        title="Adult HIV Guidelines",
        snippet="Use recommended ART regimens after clinical evaluation.",
        journal_or_publisher="clinicalinfo.hiv.gov",
        url="https://clinicalinfo.hiv.gov/example",
        evidence_type="guideline",
    )

    context = build_llm_context([item])

    assert "[1](https://clinicalinfo.hiv.gov/example) Adult HIV Guidelines" in context
    assert "https://clinicalinfo.hiv.gov/example" in context


def test_short_citation_handles_missing_author() -> None:
    item = EvidenceItem(
        id="x",
        source="europe_pmc",
        title="Example",
        journal_or_publisher="Journal",
        year=2020,
        url="https://europepmc.org/article/MED/1",
    )

    assert short_citation(item) == "Unknown author, Journal, 2020"


def test_format_citations_labels_official_health_api_sources() -> None:
    item = EvidenceItem(
        id="official_health_api:who:1",
        source="official_health_api",
        title="WHO GHO indicator: malaria incidence",
        journal_or_publisher="World Health Organization Global Health Observatory",
        year=2024,
        url="https://ghoapi.azureedge.net/api/MALARIA",
        evidence_type="official_indicator",
    )

    citations = format_citations([item])

    assert citations[0]["source_label"] == "Official Health API"
