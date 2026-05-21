# Evidence Retrieval Test Module

This is a small experimental evidence-retrieval layer for the Empirico RAG-based Clinical Decision Support System. It retrieves citation-ready medical evidence at query time and returns structured objects that can later be passed into the existing Gemini answer-generation flow.

The module does not give medical advice. It only searches, fetches, deduplicates, ranks, and formats evidence sources.

## Why APIs Instead Of Scraping

PubMed and similar scientific databases expose official APIs with stable metadata, predictable rate limits, and clear usage expectations. This experiment uses:

- NCBI E-utilities for PubMed search and metadata.
- Europe PMC REST API for open-access metadata and full-text links.
- Semantic Scholar Academic Graph API as an unauthenticated enrichment source while an API key is pending.
- Official health APIs for verified public-health context:
  - CDC Content Services API for CDC guidance/content links.
  - WHO Global Health Observatory OData API for indicator metadata and Uganda/Zambia data points.
  - World Bank Indicators API for Uganda/Zambia health-system and disease-burden indicators.
- Crawl4AI for a bounded catalogue of open public guideline/search pages when explicitly enabled. The crawler selects likely sources from the clinical question, crawls source search/seed pages, discovers relevant links, and then crawls the best matching pages.

Do not scrape PubMed search result pages by default. Broad crawling of clinical sites should go through robots.txt, legal, terms-of-use, and rate-limit review before production use.

## Structure

```text
evidence_retrieval_test/
  README.md
  requirements.txt
  .env.example
  src/
    config.py
    models.py
    providers/
      crawl_sources.json
    services/
    cli.py
    demo_api.py
  tests/
```

## Install

From the repository root:

```bash
cd healthnavy_v2
python3.11 -m venv evidence_retrieval_test/.venv
source evidence_retrieval_test/.venv/bin/activate
pip install -r evidence_retrieval_test/requirements.txt
```

Use Python 3.11+ when `ENABLE_CRAWL4AI=true`; recent Crawl4AI releases use Python 3.10+ syntax. If Crawl4AI is too heavy for a quick metadata-only test, set `ENABLE_CRAWL4AI=false`.

## Configure

```bash
cp evidence_retrieval_test/.env.example evidence_retrieval_test/.env
```

Environment variables:

```text
NCBI_API_KEY=
NCBI_TOOL_EMAIL=
SEMANTIC_SCHOLAR_API_KEY=
ENABLE_SEMANTIC_SCHOLAR=true
ENABLE_OFFICIAL_HEALTH_APIS=true
ENABLE_CRAWL4AI=false
CRAWL_ALLOWED_DOMAINS=
CRAWL_SOURCE_CATALOG_PATH=
CRAWL_MAX_SOURCES=8
CRAWL_MAX_PAGES=14
CRAWL_SEARCH_PAGES_PER_SOURCE=1
CRAWL_TIME_BUDGET_SECONDS=8
RETRIEVAL_TIME_BUDGET_SECONDS=10
REQUEST_TIMEOUT_SECONDS=20
MAX_RESULTS_PER_PROVIDER=10
```

Recommended:

- Set `NCBI_TOOL_EMAIL` for NCBI usage identification.
- Set `NCBI_API_KEY` if running repeated PubMed tests.
- Leave `ENABLE_SEMANTIC_SCHOLAR=true` while waiting for a Semantic Scholar API key; the public Academic Graph search endpoint works without authentication but can be throttled during heavy shared use.
- Leave `ENABLE_OFFICIAL_HEALTH_APIS=true` to include CDC/WHO/World Bank verified API sources. WHO and World Bank indicator results support country/burden context, not treatment guidance.
- Leave `CRAWL_ALLOWED_DOMAINS` empty to derive allowed domains from `providers/crawl_sources.json`, or set it to a stricter comma-separated allow-list.
- Keep `ENABLE_CRAWL4AI=false` for the quickest API-only test path. Set it to `true` when you specifically want approved-site crawling.
- Tune `CRAWL_MAX_SOURCES` and `CRAWL_MAX_PAGES` downward if latency is too high.
- Tune `CRAWL_TIME_BUDGET_SECONDS` to cap crawler latency; unfinished crawls are cancelled and other providers still return.
- Tune `RETRIEVAL_TIME_BUDGET_SECONDS` to cap total provider wait time for the response path.
- `CRAWL_SOURCE_CATALOG_PATH` can point to another JSON catalogue without code changes.

## Crawl Source Catalogue

The default catalogue includes Uganda/local sources first, then major international clinical sources:

- Uganda Ministry of Health Knowledge Management Portal
- Uganda Ministry of Health downloads/site search
- Infectious Diseases Institute Uganda
- Uganda Central Public Health Laboratories
- Kenya Ministry of Health and East African Community repository
- Tanzania Ministry of Health and Tanzania National Malaria Control Programme
- WHO main site and guideline pages
- WHO IRIS publications
- WHO Regional Office for Africa
- WHO policy platform
- CDC clinical guidance
- CDC Stacks
- NIH and NCBI clinical resources
- NCBI Bookshelf
- PubMed Central
- IDSA practice guidelines
- MSF Medical Guidelines
- MSF Southern Africa guidelines
- NICE Guidance
- ECDC
- Africa CDC
- UNAIDS
- PAHO
- AAFP clinical recommendations
- Severe Malaria Observatory

## Run With Docker

The main `docker-compose.yml` enables Semantic Scholar and official health APIs, while leaving `ENABLE_CRAWL4AI=false` for lower latency. Crawl4AI remains installed and can be re-enabled for approved-source crawling. Rebuild the API image after dependency changes:

```bash
docker compose build api
docker compose up api frontend
```

Crawler timings are logged by provider and end-to-end answer generation so response latency can be tracked against the sub-5-second goal.

## Run The CLI

From `healthnavy_v2`:

```bash
python -m evidence_retrieval_test.src.cli "adult patient with severe headache and fever, what should I consider?" --top-k 8
```

The CLI prints:

- A JSON response containing `items`, `citations`, `llm_context`, `provider_errors`, and `timings_ms`.
- A numbered human-readable evidence list with clickable URLs.

## Run The Demo API

```bash
uvicorn evidence_retrieval_test.src.demo_api:app --reload --port 8010
```

Request:

```bash
curl -X POST http://127.0.0.1:8010/evidence/search \
  -H "Content-Type: application/json" \
  -d '{"question":"adult patient with severe headache and fever, what should I consider?","top_k":8}'
```

Response shape:

```json
{
  "query": "adult patient with severe headache and fever, what should I consider?",
  "normalized_query": "adult severe headache fever clinical assessment red flags differential diagnosis management",
  "items": [],
  "citations": [],
  "llm_context": "Use the following evidence sources when answering...",
  "provider_errors": [],
  "timings_ms": {
    "provider.pubmed": 420.1,
    "provider.europe_pmc": 510.4,
    "provider.crawl4ai": 1850.2,
    "ranking": 0.8,
    "total": 1853.7
  }
}
```

## Query Flow

```text
User question
  -> Query builder
  -> Evidence retrieval providers
     -> PubMed / NCBI E-utilities
     -> Europe PMC REST API
     -> Semantic Scholar API, unauthenticated unless SEMANTIC_SCHOLAR_API_KEY is set
     -> Official health APIs: CDC Content Services, WHO GHO OData, World Bank Indicators
     -> Crawl4AI approved source catalogue, optional
  -> Deduplicate by DOI, PMID, PMCID, normalized title
  -> Rank by evidence strength, recency, open access, source credibility, keyword overlap
  -> Create citation-ready evidence context
  -> Gemini 2.5 Pro answer generation
  -> Answer plus clickable references
```

## Output For Existing RAG Integration

The service returns `EvidenceItem` objects with fields such as:

- `title`
- `abstract`
- `snippet`
- `authors`
- `journal_or_publisher`
- `year`
- `doi`
- `pmid`
- `pmcid`
- `url`
- `full_text_url`
- `evidence_type`
- `final_score`

Use `citation_formatter.build_llm_context(items)` to create a compact evidence block for Gemini 2.5 Pro.

Recommended answer-generation prompt pattern:

```text
You are generating clinical decision support for a clinician.
Use only the retrieved evidence below.
Cite claims with clickable markdown markers like [1](URL), [2](URL), etc.
Do not invent citations.
If evidence is missing or insufficient, say so.
Include a brief disclaimer that clinicians must verify against local guidelines and patient-specific factors.

Evidence:
{llm_context}

Question:
{user_question}
```

The frontend can render `citations` below the answer using each item's `url` as the clickable reference.

## Safety Notes

- This module retrieves evidence only; it does not diagnose or recommend treatment.
- The final LLM answer should include a clinician-facing disclaimer.
- Never fabricate citations.
- If no relevant evidence is found, return no citations.
- Log provider errors without crashing the whole search.

## Tests

Run from `healthnavy_v2`:

```bash
pytest evidence_retrieval_test/tests
```

The tests cover:

- Query normalization and expansion.
- Citation formatting and LLM context formatting.
- Deduplication by identifiers.
- Basic explainable ranking behavior.

Tests do not require live API calls.

## Before Production

Improve the following before using this in production:

- Add cache layers for repeated clinical questions and repeated crawled pages.
- Add stronger observability: structured metrics, provider error categories, and trace IDs.
- Store evidence retrieval traces for auditability.
- Add domain-specific query expansion using MeSH terms, SNOMED/ICD mappings, and local guideline preferences.
- Add provider contract tests with mocked API payloads.
- Add robots.txt and ToS review records for each crawled guideline domain.
- Add shared rate limiting across concurrent provider calls.
- Add stronger evidence grading, for example guideline source priority, study design extraction, and guideline publication/update dates.
- Add production controls for PHI minimization before sending queries to external evidence APIs.
