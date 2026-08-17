# Empirico Backend

FastAPI backend for Empirico, an evidence-backed medical information service.
The backend owns users, sessions, feedback, admin reporting, API delivery, and
evidence retrieval. Empirico calls PubMed/NCBI, Europe PMC, Semantic Scholar,
official health APIs, and Crawl4AI locally, then sends the assembled evidence
to the shared GCP Empirico Model Service for generation only.

## Runtime Path

1. A user asks a medical information question through the API.
2. `conversational_service.py` delegates to `evidence_retrieval_adapter.py`.
3. The adapter runs local evidence retrieval with enabled providers.
4. The adapter removes weak seed-only references, prioritizes real Uganda/Africa
   crawled and official web sources when relevant, and sends the filtered
   evidence to `MODEL_SERVICE_BASE_URL/v1/model/respond`.
5. Empirico rebuilds clickable numeric citations and stores/streams the answer.

## Evidence Quality Strategy

Empirico uses controlled web-RAG rather than unrestricted open-web answering:

- Retrieval is limited to configured provider APIs and allowed crawl domains.
- A source policy ranks evidence by trust tier: Uganda/local official guidance,
  WHO/AFRO and Africa-facing guidance, international guidelines, peer-reviewed
  article databases, then broad scholarly search.
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
- `EMPIRICO_ENABLE_TRUSTED_GUIDELINE_RESCUE=true`

`web` mode uses crawled/official web sources first, then PubMed/Europe PMC/
Semantic Scholar as fallback. `crawl` mode keeps only real crawled or official
web sources and drops article-database fallback results.

`EMPIRICO_EVIDENCE_COUNTRY_CODE` is optional. Leave it blank for open global
retrieval with Uganda/Africa source preference, or set it when a deployment
needs a hard country hint for local official-source routing.

`EMPIRICO_SOURCE_PREFERENCE_HINTS` expands generic searches toward Uganda
Ministry of Health, Uganda Clinical Guidelines, WHO AFRO, and East
African/African sources. `EMPIRICO_SOURCE_PREFERENCE_TERMS` controls citation
ranking for returned evidence; it is source preference, not country routing.

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
