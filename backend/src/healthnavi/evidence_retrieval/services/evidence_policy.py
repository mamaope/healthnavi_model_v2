from __future__ import annotations

from urllib.parse import urlparse


PRIMARY_CLINICAL_SOURCE_DOMAINS = {
    "health.go.ug",
    "library.health.go.ug",
    "cphl.go.ug",
    "afro.who.int",
    "africacdc.org",
    "repository.eac.int",
    "who.int",
    "iris.who.int",
    "platform.who.int",
    "medicalguidelines.msf.org",
    "msf.org.za",
    "unicef.org",
    "unaids.org",
    "cdc.gov",
    "stacks.cdc.gov",
    "clinicalinfo.hiv.gov",
    "idsociety.org",
    "nice.org.uk",
    "cks.nice.org.uk",
    "ecdc.europa.eu",
    "paho.org",
    "aafp.org",
    "ncbi.nlm.nih.gov",
    "nih.gov",
    "dailymed.nlm.nih.gov",
    "ginasthma.org",
    "goldcopd.org",
    "kdigo.org",
    "escardio.org",
    "acog.org",
    "rcog.org.uk",
    "worldgastroenterology.org",
}

ACADEMIC_DATABASE_DOMAINS = {
    "pubmed.ncbi.nlm.nih.gov",
    "pmc.ncbi.nlm.nih.gov",
    "europepmc.org",
    "semanticscholar.org",
}

SOURCE_TRUST_BONUS_BY_TIER = {
    0: 0.26,
    1: 0.22,
    2: 0.18,
    3: 0.10,
    4: 0.04,
}

EVIDENCE_TYPE_TIER = {
    "guideline": 0,
    "official_guidance": 0,
    "clinical_resource": 1,
    "systematic_review": 2,
    "clinical_trial": 3,
    "review": 4,
    "official_indicator": 5,
    "journal_article": 6,
}

EVIDENCE_TYPE_BONUS_BY_TIER = {
    0: 0.30,
    1: 0.16,
    2: 0.24,
    3: 0.20,
    4: 0.12,
    5: 0.10,
    6: 0.04,
}


def source_trust_tier(source: str, url: str, text: str = "") -> int:
    host = _host(url)
    if source == "semantic_scholar":
        return 4
    if source == "official_health_api":
        return 1
    if source in {"pubmed", "europe_pmc"} or _matches_domain(host, ACADEMIC_DATABASE_DOMAINS):
        return 3
    if _matches_domain(host, PRIMARY_CLINICAL_SOURCE_DOMAINS):
        return 1
    return 9


def evidence_type_tier(evidence_type: str | None) -> int:
    return EVIDENCE_TYPE_TIER.get((evidence_type or "").strip().lower(), 8)


def source_trust_bonus(source: str, url: str, text: str = "") -> float:
    return SOURCE_TRUST_BONUS_BY_TIER.get(source_trust_tier(source, url, text), 0.0)


def evidence_type_bonus(evidence_type: str | None) -> float:
    return EVIDENCE_TYPE_BONUS_BY_TIER.get(evidence_type_tier(evidence_type), 0.0)


def evidence_policy_sort_key(
    *,
    source: str,
    evidence_type: str | None,
    url: str,
    text: str = "",
) -> tuple[int, int]:
    return (
        source_trust_tier(source, url, text),
        evidence_type_tier(evidence_type),
    )


def _host(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host.removeprefix("www.")


def _matches_domain(host: str, domains: set[str]) -> bool:
    return any(host == domain or host.endswith(f".{domain}") for domain in domains)
