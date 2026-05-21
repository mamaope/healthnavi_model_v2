from __future__ import annotations

from evidence_retrieval_test.src.models import EvidenceItem


SOURCE_LABELS = {
    "pubmed": "PubMed",
    "europe_pmc": "Europe PMC",
    "semantic_scholar": "Semantic Scholar",
    "official_health_api": "Official Health API",
    "crawl4ai": "Guideline Page",
}


def format_citations(items: list[EvidenceItem]) -> list[dict[str, object]]:
    return [
        {
            "number": index,
            "title": item.title,
            "source_label": SOURCE_LABELS.get(_source_key(item), _source_key(item)),
            "journal": item.journal_or_publisher,
            "year": item.year,
            "url": str(item.url),
            "markdown_citation": f"[{index}]({item.url})",
            "doi": item.doi,
            "short_citation": short_citation(item),
            "why_relevant": why_relevant(item),
        }
        for index, item in enumerate(items, start=1)
    ]


def build_llm_context(items: list[EvidenceItem]) -> str:
    lines = [
        "Use the following evidence sources when answering.",
        "Cite claims with clickable markdown citation markers like [1](URL), [2](URL), etc.",
        "Do not invent citations. If the evidence is insufficient, say so clearly.",
    ]
    for index, item in enumerate(items, start=1):
        abstract_or_snippet = (item.abstract or item.snippet or "").replace("\n", " ")
        if len(abstract_or_snippet) > 1200:
            abstract_or_snippet = f"{abstract_or_snippet[:1197]}..."
        lines.append(
            f"[{index}]({item.url}) {item.title} - {item.journal_or_publisher or SOURCE_LABELS.get(_source_key(item), _source_key(item))} "
            f"- {item.year or item.publication_date or 'n.d.'} - {item.url} - {abstract_or_snippet}"
        )
    return "\n".join(lines)


def short_citation(item: EvidenceItem) -> str:
    first_author = "Unknown author"
    if item.authors:
        first_author = item.authors[0].split()[-1]
        if len(item.authors) > 1:
            first_author = f"{first_author} et al."
    venue = item.journal_or_publisher or SOURCE_LABELS.get(_source_key(item), _source_key(item))
    year = item.year or item.publication_date or "n.d."
    return f"{first_author}, {venue}, {year}"


def why_relevant(item: EvidenceItem) -> str:
    evidence_type = (item.evidence_type or "evidence").replace("_", " ")
    if item.evidence_type == "guideline":
        return "Provides guideline-level clinical recommendations relevant to the query."
    if item.evidence_type == "systematic_review":
        return "Summarizes multiple studies relevant to the clinical question."
    if item.evidence_type == "clinical_trial":
        return "Reports trial evidence relevant to treatment decisions."
    if item.snippet:
        return "Contains an evidence snippet matching the clinical query."
    return f"Provides {evidence_type} metadata and abstract content relevant to the query."


def _source_key(item: EvidenceItem) -> str:
    return getattr(item.source, "value", str(item.source))
