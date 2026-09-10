# Empirico Backend

FastAPI backend for Empirico, an evidence-backed medical information service.
The backend owns users, sessions, feedback, admin reporting, API delivery, and
evidence retrieval. Docker/local app runs use the shared Empirico Model Service
only for answer generation after local PubMed/NCBI, Europe PMC, Semantic
Scholar, official health API, and Crawl4AI retrieval has selected the evidence.

## Runtime Path

1. A user asks a medical information question through the API.
2. `conversational_service.py` delegates to `evidence_retrieval_adapter.py`.
3. The adapter retrieves evidence with enabled local providers, prioritizing
   current, topic-relevant crawled and official web sources.
4. If the first pass has no usable citations, the adapter runs bounded rescue
   retrieval.
5. The adapter sends the selected evidence to
   `MODEL_SERVICE_BASE_URL/v1/model/respond`.
6. Empirico rebuilds clickable numeric citations, returns only cited selected
   sources in the References list, and stores/streams the answer.

## Evidence Quality Strategy

Empirico uses controlled web-RAG rather than unrestricted open-web answering:

- Retrieval is limited to configured provider APIs and allowed crawl domains.
- A source policy ranks evidence by trust tier: official guidance, international
  guidelines, peer-reviewed article databases, then broad scholarly search.
- Quick search targets 4 unique answer sources and uses fewer crawl/provider
  resources. Deep search targets 8 unique answer sources and searches more
  resources.
- Deployment-specific source preferences are optional and apply only when the
  user question or supplied context mentions that scope. Generic clinical
  questions stay neutral.
- Within comparable evidence, newer references are preferred over older ones.
- Evidence type is ranked separately: guidelines and official guidance before
  systematic reviews, trials, reviews, and ordinary articles.
- Static HTML guideline fetches are cached so repeated local/prod queries are
  faster and more reproducible. Set `CRAWL_CACHE_TTL_SECONDS=-1` to disable the
  cache.
- Generated citations are rebuilt by Empirico, so every clickable inline marker
  maps to a retrieved source URL.
- `backend/evaluation/web_rag_smoke.json` contains cross-domain medical smoke
  cases. Run `PYTHONPATH=src python scripts/evaluate_web_rag.py --limit 3`
  from `backend/` to check retrieval/generation behavior.

## Required Environment

- `SECRET_KEY`, `ENCRYPTION_KEY`
- `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`
- `MODEL_SERVICE_BASE_URL`
- `MODEL_SERVICE_API_KEY`
- `MODEL_SERVICE_TIMEOUT_SECONDS`
- Provider keys and toggles when local retrieval is enabled:
  `NCBI_API_KEY`, `NCBI_TOOL_EMAIL`, `SEMANTIC_SCHOLAR_API_KEY`,
  `ENABLE_PUBMED`, `ENABLE_EUROPE_PMC`, `ENABLE_SEMANTIC_SCHOLAR`,
  `ENABLE_OFFICIAL_HEALTH_APIS`, `ENABLE_CRAWL4AI`
- `CRAWL_CACHE_DIR`, `CRAWL_CACHE_TTL_SECONDS`
- `EMPIRICO_EVIDENCE_COUNTRY_CODE`
- `EMPIRICO_SOURCE_PREFERENCE_HINTS`
- `EMPIRICO_SOURCE_PREFERENCE_TERMS`
- `EMPIRICO_EVIDENCE_PROVIDER_MODE=web`
- `EMPIRICO_QUICK_EVIDENCE_PROVIDER_MODE=crawl`
- `EMPIRICO_DEEP_EVIDENCE_PROVIDER_MODE=web`
- `EMPIRICO_ENABLE_EVIDENCE_RESCUE=true`
- `EMPIRICO_QUICK_LATENCY_TARGET_SECONDS=14.5`
- `EMPIRICO_QUICK_MODEL_TIMEOUT_SECONDS=30` (floor 8s)
- `EMPIRICO_DEEP_MODEL_TIMEOUT_SECONDS=120` (floor 30s)
- `EMPIRICO_ANSWER_TEMPERATURE=0.2`
- `EMPIRICO_QUICK_MAX_REFERENCES=4` / `EMPIRICO_DEEP_MAX_REFERENCES=8`
- `EMPIRICO_QUICK_CONTEXT_SOURCES=12` / `EMPIRICO_DEEP_CONTEXT_SOURCES=20`
- `EMPIRICO_QUICK_RETRIEVAL_EARLY_STOP=true`
- `EMPIRICO_QUICK_RETRIEVAL_EARLY_STOP_WAIT_SECONDS=1.5`
- `EMPIRICO_QUICK_RESCUE_MIN_SECONDS=2.5`
- `EMPIRICO_QUICK_MAX_OUTPUT_TOKENS=2000`
- `EMPIRICO_DEEP_MAX_OUTPUT_TOKENS=5000`
- `EMPIRICO_QUICK_ANSWER_TOP_K=4`
- `EMPIRICO_DEEP_ANSWER_TOP_K=8`
- `EMPIRICO_QUICK_SEARCH_TOP_K=8`
- `EMPIRICO_DEEP_SEARCH_TOP_K=24`
- `EMPIRICO_QUICK_CRAWL_MAX_SOURCES=4`
- `EMPIRICO_DEEP_CRAWL_MAX_SOURCES=8`
- `EMPIRICO_QUICK_CRAWL_TIME_BUDGET_SECONDS=8`
- `EMPIRICO_DEEP_CRAWL_TIME_BUDGET_SECONDS=14`
- `EMPIRICO_QUICK_RETRIEVAL_TIME_BUDGET_SECONDS=10`
- `EMPIRICO_DEEP_RETRIEVAL_TIME_BUDGET_SECONDS=18`
- `EMPIRICO_QUICK_MAX_RESULTS_PER_PROVIDER=4`
- `EMPIRICO_DEEP_MAX_RESULTS_PER_PROVIDER=8`

`web` local-provider mode uses crawled/official web sources first, then
PubMed/Europe PMC/Semantic Scholar as fallback. `crawl` mode keeps only real
crawled or official web sources and drops article-database fallback results.
The retrieved evidence is then passed to the shared model service for answer
generation and presentation.

`EMPIRICO_ENABLE_EVIDENCE_RESCUE=true` prevents empty evidence responses by
retrying failed citation retrieval with the broader web provider mix. If no
verified source URLs are available, Empirico answers without citations instead
of attaching metadata-only source links.

`EMPIRICO_EVIDENCE_COUNTRY_CODE=UG` is the default for the Uganda deployment.
It prioritizes Uganda official and national sources while still allowing global
fallback evidence. Set it to `GLOBAL` only for deliberately global/open
retrieval.

`EMPIRICO_SOURCE_PREFERENCE_HINTS` and `EMPIRICO_SOURCE_PREFERENCE_TERMS`
default to a Uganda-first source hierarchy: Ministry of Health Knowledge
Management Portal, Uganda Clinical Guidelines, NDA, UNIPH, CPHL/NHLDS,
specialist Ugandan institutions, WHO AFRO/East Africa, then global fallback
sources. Explicit user requests for another jurisdiction can override this.

Provider credentials for PubMed/NCBI, Semantic Scholar, official APIs, and
Crawl4AI belong in the Empirico app runtime because this app calls those
providers directly. Vertex/model credentials belong on the shared model-service
runtime. Legacy Azure OpenAI and Milvus settings should stay commented unless a
new local feature explicitly reintroduces them.

The default Docker image skips Whisper/Torch so local rebuilds stay fast. Build
with `INSTALL_TRANSCRIPTION=true` only when testing voice transcription.

Google OAuth and SMTP settings are optional unless those features are enabled.
Whisper settings are only needed for voice transcription.

## Development

```bash
pip install -r requirements.txt
alembic upgrade head
uvicorn healthnavi.main:app --reload
```

For Docker-based local development, use the root `docker-compose.yml`.

Evidence retrieval tests:

```bash
PYTHONPATH=src python -m pytest tests/unit/test_evidence_retrieval_adapter.py -q
EMPIRICO_LIVE_EVIDENCE_TESTS=true PYTHONPATH=src python -m pytest tests/unit/test_evidence_retrieval_adapter.py -q -k live_crawl
```

The live/cached crawl test is opt-in so normal unit tests stay deterministic,
but it exercises the real crawl catalog and verifies retrieved evidence can be
ranked and cited.
