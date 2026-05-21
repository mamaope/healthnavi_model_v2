from evidence_retrieval_test.src.models import EvidenceItem
from evidence_retrieval_test.src.services.evidence_ranker import (
    deduplicate_items,
    rank_evidence_items,
)


def test_deduplicate_items_prefers_identifier_matches() -> None:
    first = EvidenceItem(
        id="pubmed:1",
        source="pubmed",
        title="Same Trial",
        doi="10.1000/same",
        pmid="1",
        url="https://pubmed.ncbi.nlm.nih.gov/1/",
    )
    duplicate = EvidenceItem(
        id="europe:1",
        source="europe_pmc",
        title="Same Trial",
        doi="10.1000/same",
        pmid="1",
        url="https://europepmc.org/article/MED/1",
    )

    assert deduplicate_items([first, duplicate]) == [first]


def test_deduplicate_items_handles_same_doi_with_different_title() -> None:
    first = EvidenceItem(
        id="pubmed:1",
        source="pubmed",
        title="HIV Therapy Trial",
        doi="10.1000/same",
        url="https://pubmed.ncbi.nlm.nih.gov/1/",
    )
    duplicate = EvidenceItem(
        id="semantic:1",
        source="semantic_scholar",
        title="A Trial of HIV Therapy",
        doi="https://doi.org/10.1000/same",
        url="https://www.semanticscholar.org/paper/1",
    )

    assert deduplicate_items([first, duplicate]) == [first]


def test_ranking_prioritizes_guidelines_and_recent_open_access() -> None:
    old_article = EvidenceItem(
        id="pubmed:old",
        source="pubmed",
        title="HIV treatment historical article",
        abstract="HIV treatment therapy.",
        year=1998,
        url="https://pubmed.ncbi.nlm.nih.gov/2/",
        evidence_type="journal_article",
    )
    guideline = EvidenceItem(
        id="crawl4ai:guideline",
        source="crawl4ai",
        title="HIV antiretroviral therapy adult guidelines",
        snippet="Adult HIV treatment uses antiretroviral therapy regimens.",
        year=2025,
        url="https://clinicalinfo.hiv.gov/example",
        full_text_url="https://clinicalinfo.hiv.gov/example",
        open_access=True,
        evidence_type="guideline",
    )

    ranked = rank_evidence_items("HIV treatment adult antiretroviral therapy guidelines", [old_article, guideline])

    assert ranked[0].id == "crawl4ai:guideline"
    assert ranked[0].final_score is not None
    assert ranked[0].final_score > ranked[1].final_score


def test_ranking_can_use_provider_corrected_query() -> None:
    typo_query = "how to manage menstration in girls"
    unrelated = EvidenceItem(
        id="pubmed:trauma",
        source="pubmed",
        title="The Capacity to Manage Orthopaedic Trauma",
        abstract="Hospital systems for trauma care in boys and girls.",
        year=2015,
        url="https://pubmed.ncbi.nlm.nih.gov/1/",
        evidence_type="journal_article",
        raw={"query_used": typo_query},
    )
    corrected_match = EvidenceItem(
        id="pubmed:menstruation",
        source="pubmed",
        title="Menstruation management in adolescent girls",
        abstract="Guidance for menstrual hygiene and menstruation symptoms in girls.",
        year=2024,
        url="https://pubmed.ncbi.nlm.nih.gov/2/",
        evidence_type="review",
        raw={"query_used": "how to manage menstruation in girls"},
    )

    ranked = rank_evidence_items(typo_query, [unrelated, corrected_match])

    assert ranked[0].id == "pubmed:menstruation"


def test_ranking_prioritizes_local_and_regional_sources_broadly() -> None:
    global_guideline = EvidenceItem(
        id="global:guideline",
        source="crawl4ai",
        title="Pediatric fever treatment guideline",
        snippet="Treatment guidance for fever in children.",
        year=2025,
        url="https://example.org/pediatric-fever-guideline",
        evidence_type="guideline",
    )
    uganda_guideline = EvidenceItem(
        id="uganda:guideline",
        source="crawl4ai",
        title="Uganda pediatric fever treatment guideline",
        snippet="Treatment guidance for fever in children in Uganda.",
        year=2024,
        url="https://health.go.ug/example-guideline",
        evidence_type="guideline",
    )

    ranked = rank_evidence_items("treatment of fever in a 2 year old child", [global_guideline, uganda_guideline])

    assert ranked[0].id == "uganda:guideline"
