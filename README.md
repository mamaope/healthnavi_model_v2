# Empirico - AI-Powered Medical Knowledge Base

<div align="center">

![Empirico Logo](https://via.placeholder.com/200x60?text=Empirico)

**Empirico** is a secure AI-powered medical information system with shared Empirico Model Service evidence/generation and local retrieval/crawling fallback.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)](https://www.postgresql.org/)

</div>

---

## 📋 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [API Documentation](#api-documentation)
- [Platforms](#platforms)
- [Security & Compliance](#security--compliance)
- [Development](#development)
- [Testing](#testing)
- [Contributing](#contributing)
- [Support](#support)
- [License](#license)

---

## 🎯 Overview

**Empirico** is a medical information platform designed to help users access evidence-backed medical answers through AI-powered assistance. This app owns the user experience, authentication, sessions, citation rebuilding, response display, and evidence retrieval. For evidence answers, the backend retrieves local/crawled/provider evidence first, then sends that evidence to the shared model service for answer generation.

### What Empirico Does

- **Medical Information Access**: Provides AI-powered access to evidence-based medical information, treatment planning, and clinical queries
- **Drug Information**: Access comprehensive drug dosing, interactions, and prescribing information
- **Clinical Guidelines**: References to WHO, ADA, and other authoritative medical guidelines
- **Evidence-Based Answers**: Retrieves and ranks evidence locally with crawled/provider sources, then delegates final answer generation to the shared Empirico Model Service
- **Multi-Platform Access**: Available on web and mobile (Android) platforms

---

## ✨ Key Features

### 🔐 Authentication & User Management
- **Multiple Authentication Methods**
  - Email/password registration and login
  - Google Sign-In (OAuth 2.0) for web and mobile
  - Secure JWT-based session management
  - Password reset functionality
  - Email verification
- **User Roles**: Support for healthcare professionals, administrators, and super admins
- **Account Management**: Profile management, account closure, and data deletion requests

### 💬 AI-Powered Medical Information Chat
- **Interactive Chat Interface**: Real-time conversation with AI medical information assistant
- **Deep Search Mode**: Enhanced search capabilities for comprehensive responses
- **Session Management**: Create and manage multiple conversation sessions
- **Message History**: Complete conversation history with search capabilities
- **Rich Formatting**: Markdown support with proper medical formatting, aligned between web and Android (headings, spacing, lists, blockquotes)
- **Feedback System**: Rate responses as helpful/not helpful to improve the system

### 📊 Survey & Research
- **Pilot Program Surveys**: Baseline, mid-pilot, and final surveys
- **PMF (Product-Market Fit) Analysis**: Integrated survey system for product validation
- **Survey Management**: Admin dashboard for survey configuration and visibility

### 📱 Multi-Platform Support
- **Web Application**: React-based responsive web interface
- **Android Mobile App**: Native Android app with offline capabilities
- **Cross-Platform Sync**: Seamless synchronization across devices

### 🔒 Security & Compliance
- **HIPAA Compliance**: Protected Health Information (PHI) encryption and audit logging
- **GDPR Compliance**: Data protection and privacy controls
- **ISO 13485**: Medical device software quality management
- **SOC 2 Type II**: Security, availability, and confidentiality controls
- **Data Encryption**: AES-256 encryption for sensitive medical data
- **Audit Trails**: Complete audit logging for compliance

### 📈 Admin Dashboard
- **User Management**: User administration and role management
- **Device Statistics**: Track device types (phone, tablet, laptop) for analytics
- **Session Analytics**: Monitor usage patterns and system health
- **Survey Management**: Configure and manage survey programs

---

## 🏗️ Architecture

### System Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Frontend  │    │   FastAPI       │    │   PostgreSQL    │
│   (React/Vite)  │◄──►│   Backend       │◄──►│   Database      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                      │                        │
         │                      │                        │
         │                      ▼                        │
         │              ┌─────────────────┐             │
         │              │ Shared Empirico │             │
         │              │ Model Service   │             │
         │              └─────────────────┘             │
         │                                              │
         └──────────────────────────────────────────────┘
                    ┌─────────────────┐
                    │  Android App    │
                    │  (Kotlin)       │
                    └─────────────────┘
```

### Technology Stack

**Backend**
- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 15+
- **Model Service**: Shared Empirico Model Service over HTTPS
- **Authentication**: JWT, OAuth 2.0
- **ORM**: SQLAlchemy
- **Migrations**: Alembic

**Frontend (Web)**
- **Framework**: React with TypeScript
- **Build Tool**: Vite
- **UI Library**: Material UI components
- **State Management**: React hooks and context
- **HTTP Client**: Axios

**Mobile (Android)**
- **Language**: Kotlin
- **UI Framework**: Jetpack Compose
- **Architecture**: MVVM (Model-View-ViewModel)
- **Networking**: Retrofit + OkHttp
- **Navigation**: Jetpack Navigation Compose

**Infrastructure**
- **Containerization**: Docker & Docker Compose
- **Model Backend**: Shared GCP-hosted Empirico Model Service

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **PostgreSQL 15+**
- **Docker & Docker Compose** (recommended)
- **Shared Empirico Model Service URL and API key**
- **Node.js 18+** (for frontend development)
- **Android Studio** (for mobile development)

### Docker Deployment (Recommended)

The Docker stack runs only the services this app owns: Postgres, the FastAPI
backend, and the web frontend. The shared Empirico Model Service stays in GCP
and is reached over HTTPS using `MODEL_SERVICE_BASE_URL` / `MODEL_SERVICE_API_KEY`.

There are two compose files, used the same way as in healthnavy-v3:

| File | Use | Backend | Frontend |
|------|-----|---------|----------|
| `docker-compose.yml` | Local development (default) | uvicorn `--reload`, code bind-mounted | Vite dev server on `:3000` |
| `docker-compose-prod.yml` | Production / staging server | uvicorn without reload | Built static bundle served by nginx on `:3000` |

**Development** (from `/Users/richkitibwa/Documents/mamaope/empirico/healthnavy_v2`):

```bash
# Create/edit .env first if this is a fresh checkout.
# Required basics: DB_USER, DB_PASSWORD, DB_NAME, SECRET_KEY,
# ENCRYPTION_KEY, MODEL_SERVICE_BASE_URL, MODEL_SERVICE_API_KEY.

docker compose up -d --build          # start db + api + frontend
docker compose logs -f api            # follow backend logs
docker compose down                   # stop (keeps the postgres volume)
```

Backend code changes are picked up automatically because `./backend` is
mounted into the container and uvicorn runs with `--reload`.

**Production** (the `-f` flag selects the prod compose file):

```bash
docker compose -f docker-compose-prod.yml up -d --build
docker compose -f docker-compose-prod.yml logs -f api
docker compose -f docker-compose-prod.yml down
```

Set `ENV=production`, `DEBUG=false`, `BACKEND_URL`, `FRONTEND_URL` and the
production `CORS_ORIGINS` in `.env` before starting the prod stack. There is no
separate "prod flag" beyond choosing the compose file; both files read the same
`.env`.

URLs once running:

```text
Web:      http://localhost:3000
API:      http://localhost:8050/api/v2
API docs: http://localhost:8050/api/v2/docs
Health:   http://localhost:8050/api/v2/health
```

Smoke test an answer without the UI (guest access is allowed):

```bash
curl -s -X POST http://localhost:8050/api/v2/diagnosis/diagnose \
  -H "Content-Type: application/json" \
  -d '{"patient_data":"First-line ART for a 30 year old woman in Kampala?","deep_search":false}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['model_response'])"
```

The default API image is intentionally lean. It does not install Whisper/Torch
or browser automation dependencies. To include voice transcription dependencies,
build with `INSTALL_TRANSCRIPTION=true docker compose up -d --build`.

On first run, the API container runs database migrations and seeds an admin user if none exists (override with `ADMIN_EMAIL`, `ADMIN_PASSWORD`, etc. in `.env`). To seed an admin manually: `cd backend && python scripts/seed_admin_user.py`.

### Local Dev Without Docker

Use this when you want the backend/frontend running directly on your machine
and Postgres is already available.
From `/Users/richkitibwa/Documents/mamaope/empirico`, run:

```bash
cd healthnavy_v2/backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=src
alembic upgrade head
uvicorn healthnavi.main:app --reload --host 0.0.0.0 --port 8050
```

In a second terminal:

```bash
cd healthnavy_v2/frontend
corepack enable
pnpm install
pnpm run dev
```

Local URLs:
- Web via Docker: `http://localhost:3000`
- Web via Vite dev server: `http://localhost:5173`
- API: `http://localhost:8050/api/v2`
- API docs: `http://localhost:8050/api/v2/docs`

---

## 📦 Installation

### Backend Setup

1. **Create virtual environment**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. **Run database migrations**
```bash
alembic upgrade head
```

5. **Seed admin user** (optional, if not using Docker)
```bash
python scripts/seed_admin_user.py
```

6. **Start the backend**
```bash
uvicorn healthnavi.main:app --reload --host 0.0.0.0 --port 8050
```

### Frontend Setup

1. **Install dependencies**
```bash
cd frontend
npm install
```

2. **Start development server**
```bash
npm run dev
```

3. **Access the application**
```
http://localhost:5173
```

### Mobile App Setup

1. **Open in Android Studio**
```bash
cd mobile
# Open the project in Android Studio
```

2. **Configure API URL** (if using local backend)
   - Edit `local.properties` or `gradle.properties`
   - Set `API_BASE_URL=http://10.0.2.2:8050/api/v2/` (emulator)
   - Or use your machine's IP for physical devices

3. **Build and run**
```bash
./gradlew assembleDebug
./gradlew installDebug
```

---

## ⚙️ Configuration

### Required Environment Variables

```bash
# Security
SECRET_KEY=your-super-secure-secret-key-min-32-chars
ENCRYPTION_KEY=your-encryption-key-min-32-chars

# Database
DB_USER=empirico_user
DB_PASSWORD=your-secure-db-password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=empirico_cdss

# Google OAuth (for authentication)
GOOGLE_CLIENT_ID=your-web-oauth-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=https://your-domain.com/api/v2/auth/google/callback

# Shared Empirico Model Service
MODEL_SERVICE_BASE_URL=https://empirico-model-service-e2dgjxq3uq-ew.a.run.app
MODEL_SERVICE_API_KEY=your-model-service-api-key
MODEL_SERVICE_TIMEOUT_SECONDS=180

# Answer generation (one model call per answer)
EMPIRICO_QUICK_MODEL_TIMEOUT_SECONDS=30      # floor 8s; smaller values are ignored
EMPIRICO_DEEP_MODEL_TIMEOUT_SECONDS=120      # floor 30s
EMPIRICO_QUICK_MAX_OUTPUT_TOKENS=2000
EMPIRICO_DEEP_MAX_OUTPUT_TOKENS=5000
EMPIRICO_ANSWER_TEMPERATURE=0.2
EMPIRICO_QUICK_MAX_REFERENCES=4              # distinct documents cited per answer
EMPIRICO_DEEP_MAX_REFERENCES=8
EMPIRICO_QUICK_CONTEXT_SOURCES=12            # passages shown to the model
EMPIRICO_DEEP_CONTEXT_SOURCES=20

# Evidence retrieval budgets (bounded by the quick latency target)
EMPIRICO_QUICK_LATENCY_TARGET_SECONDS=14.5
EMPIRICO_QUICK_ANSWER_TOP_K=4                # "enough sources" threshold for early stop
EMPIRICO_DEEP_ANSWER_TOP_K=8
EMPIRICO_QUICK_SEARCH_TOP_K=8
EMPIRICO_DEEP_SEARCH_TOP_K=24
EMPIRICO_EVIDENCE_COUNTRY_CODE=UG
EMPIRICO_SOURCE_PREFERENCE_HINTS=Uganda Ministry of Health Knowledge Management Portal Uganda Clinical Guidelines health.go.ug library.health.go.ug NDA UNIPH CPHL NHLDS Uganda WHO AFRO East Africa Africa
EMPIRICO_SOURCE_PREFERENCE_TERMS=uganda,ugandan,health.go.ug,library.health.go.ug,nda.or.ug,uniph.go.ug,cphl.go.ug,qadash.cphl.go.ug,uci.or.ug,ulii.org,idi.mak.ac.ug,elearning.idi.co.ug,uganda clinical guidelines,ministry of health uganda,national drug authority uganda,uganda national institute of public health,uganda cancer institute,who afro,afro.who.int,east africa,africa
EMPIRICO_EVIDENCE_PROVIDER_MODE=web
EMPIRICO_ENABLE_EVIDENCE_RESCUE=true
EMPIRICO_QUICK_RETRIEVAL_EARLY_STOP=true
EMPIRICO_QUICK_RETRIEVAL_EARLY_STOP_WAIT_SECONDS=1.5
EMPIRICO_QUICK_RESCUE_MIN_SECONDS=2.5
EMPIRICO_QUICK_ENABLE_RETRIEVAL_PLANNER=true
EMPIRICO_DEEP_ENABLE_RETRIEVAL_PLANNER=true
EMPIRICO_QUICK_CRAWL_MAX_SOURCES=4
EMPIRICO_DEEP_CRAWL_MAX_SOURCES=8
EMPIRICO_QUICK_CRAWL_TIME_BUDGET_SECONDS=8
EMPIRICO_DEEP_CRAWL_TIME_BUDGET_SECONDS=14
EMPIRICO_QUICK_RETRIEVAL_TIME_BUDGET_SECONDS=10
EMPIRICO_DEEP_RETRIEVAL_TIME_BUDGET_SECONDS=18
EMPIRICO_QUICK_MAX_RESULTS_PER_PROVIDER=4
EMPIRICO_DEEP_MAX_RESULTS_PER_PROVIDER=8

# Local evidence providers called by Empirico
NCBI_API_KEY=your-ncbi-api-key
NCBI_TOOL_EMAIL=you@example.com
SEMANTIC_SCHOLAR_API_KEY=your-semantic-scholar-api-key
ENABLE_PUBMED=true
ENABLE_EUROPE_PMC=true
ENABLE_SEMANTIC_SCHOLAR=true
ENABLE_OFFICIAL_HEALTH_APIS=true
ENABLE_CRAWL4AI=true
ENABLE_CRAWL4AI_BROWSER=false
CRAWL_ALLOWED_DOMAINS=health.go.ug,library.health.go.ug,nda.or.ug,uniph.go.ug,cphl.go.ug,qadash.cphl.go.ug,uci.or.ug,ulii.org,differentiatedservicedelivery.org,who.int,iris.who.int,platform.who.int,afro.who.int,cdc.gov,stacks.cdc.gov,nih.gov,ncbi.nlm.nih.gov,idsociety.org,medicalguidelines.msf.org,nice.org.uk,ecdc.europa.eu,africacdc.org,unaids.org,paho.org,aafp.org,unicef.org,reliefweb.int
CRAWL_MAX_SOURCES=8
CRAWL_MAX_PAGES=14
CRAWL_SEARCH_PAGES_PER_SOURCE=1
CRAWL_TIME_BUDGET_SECONDS=14
RETRIEVAL_TIME_BUDGET_SECONDS=18
REQUEST_TIMEOUT_SECONDS=20
MAX_RESULTS_PER_PROVIDER=10

# Application
ENV=production
DEBUG=false
LOG_LEVEL=INFO
CORS_ORIGINS=["https://your-frontend-domain.com"]

# Production (when behind nginx/reverse proxy)
BACKEND_URL=https://empirico.ai
FRONTEND_URL=https://empirico.ai
```

### How an answer is produced

1. **Plan** (one small model call): the question is turned into 1-4 retrieval
   queries that keep the user's qualifiers (population, place, drug, setting).
   The plan also names the **condition**, which is what the question is about.
   A query string alone cannot say which of its words is the subject: in the
   catalogue "first-line" is rarer than "hypertension", so matching on raw
   terms sent a hypertension question to the tuberculosis source. The condition
   is passed to retrieval as a topic hint and decides which sources are
   crawled and which passages survive relevance filtering.
2. **Retrieve** locally, all providers concurrently: crawled guideline
   pages/PDFs (Uganda MoH, NDA, WHO, CDC, NICE, ...), official health APIs,
   PubMed, Europe PMC and Semantic Scholar, bounded by
   `EMPIRICO_QUICK_LATENCY_TARGET_SECONDS`. Two rules govern the crawl:
   - The budget is split between sources that index the condition and the broad
     national portals, alternating, so neither group can take every slot. Before
     this, four generic portals were crawled for a diabetes question and no
     diabetes source was visited.
   - Each source is **searched for the question** before its pinned seed URLs
     are fetched. A seed is a document someone pinned once, so it answers every
     query with the same page: the NICE entry pins the hypertension guideline,
     and a diabetes question was crawling it. Seeds now fill leftover budget.
3. **Select candidates** deterministically, with no model call and no
   condition-specific rules:
   - Off-topic pages, statistics indicators, cover pages, running heads and
     tables of figures are dropped. A passage qualifies on shape, not length,
     so a one-line dosing rule survives and a document title does not.
   - Once any passage of a document is relevant the document is, so its other
     passages are re-admitted. The page carrying the dose often does not repeat
     the condition name; the chapter heading did that.
   - Passages are ordered by source authority (Uganda national > WHO and other
     primary guidance > article databases), then evidence type, then whether the
     passage states doses, thresholds or durations rather than only naming a
     pathway, then jurisdiction, then how recent the document is, then retrieval
     score. That order is the trade-off: an older national manual that gives the
     regimen outranks a newer page that only names it, a local document outranks
     a foreign one of equal usefulness even when the foreign one is newer, and
     recency then decides between comparable editions. Jurisdiction is matched
     on the document's own title, publisher and URL, never on its body text, so
     a study that merely mentions Kampala is not treated as national guidance.
   - A reference labelled with a site name rather than a document name is
     relabelled from the URL path when the path names the document.
   - The best passage of each document is taken before a second from any, and
     further passages are chosen by maximal marginal relevance so one guideline
     does not fill every slot with the same viewpoint.
   - Up to `EMPIRICO_*_CONTEXT_SOURCES` passages from at most
     `EMPIRICO_*_MAX_REFERENCES + 2` documents go to the model.
4. **Generate** (one model call, `EMPIRICO_*_MODEL_TIMEOUT_SECONDS`): the
   prompt in `backend/src/healthnavi/core/constants.py` opens with the rule the
   answer is judged on, **answer at the lowest actionable level**. A category is
   never the answer: "an antibiotic", "imaging", "supportive care" and
   "referral" name a box, and the answer opens it, giving the medicine with dose
   route frequency and duration, the actual test, the actual fluid or feed. Where
   a class genuinely is the answer it is named with the agents used from it, and
   where the sources stop at the class the last step comes from clinical
   knowledge, unmarked. Vague verbs such as "assess", "monitor closely" or
   "consider antibiotics" are replaced by what is measured, how often, against
   what target, and what is given. It then sets the answer contract. Every management answer states the **decision** (which patients
   take which path and what decides it), the **action** (what is actually given
   or done, with amounts) and the **endpoint** (when to change, stop, refer or
   discharge), states steps common to every path once rather than per path,
   covers every subgroup the question named, and continues from
   established clinical knowledge where the sources stop, leaving those
   sentences unmarked. Naming a setting, programme or pathway does not count as
   an answer, and the reader is never sent to a table or annex. Quick answers
   target 120-250 words; deep answers 400-900.
5. **Finalize** (`backend/src/healthnavi/services/answer_composer.py`): markers
   are validated against the retrieved sources, renumbered in order of first
   use, linked as `[n](url)`, and a `**References**` list of the cited sources
   is built from the source metadata. Pages of one document share a reference
   number (each inline link still opens the exact page), and at most
   `EMPIRICO_QUICK_MAX_REFERENCES` (4) or `EMPIRICO_DEEP_MAX_REFERENCES` (8)
   distinct documents are cited. The model's prose is never rewritten.

**References are not optional.** If the first pass produces no citable source,
retrieval is retried with every gate removed: the quick latency budget, the
deployment's provider mode and the country filter are all worth less than a
citation, because an uncited answer is the one a clinician cannot check. The
retry is only as good as what exists, so a passage still has to match the
question's subject on more than one word when the subject has more than one:
citing otitis media guidance for a malnutrition question, on the shared word
"acute", is worse than citing nothing.

The answer never sends the reader elsewhere. It does not say which parts the
sources missed, and it never tells them to check, consult or verify against a
guideline: they asked so they would not have to read it. Where the sources stop,
the answer continues from established clinical knowledge with those sentences
unmarked. If the model call fails after one retry the API returns a short error;
nothing is stitched together from raw crawled text.

`EMPIRICO_EVIDENCE_PROVIDER_MODE=web` controls the local providers: crawled and
official web sources first, with PubMed/Europe PMC/Semantic Scholar as fallback.
Quick mode defaults to `EMPIRICO_QUICK_EVIDENCE_PROVIDER_MODE=web`; deep mode
defaults to `EMPIRICO_DEEP_EVIDENCE_PROVIDER_MODE=web`. Use `crawl` globally
only when the deployment should refuse article-database fallback results.

`EMPIRICO_ENABLE_EVIDENCE_RESCUE=true` keeps answers from dead-ending: if the
normal quick/deep retrieval path returns no usable citations, Empirico retries
with the broader web provider mix before asking the model to answer without
citations if no verified source URLs are available.

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
providers directly. `MODEL_SERVICE_BASE_URL` only controls where the final
generation request is sent. Legacy Azure OpenAI and Milvus settings should stay
commented unless a new local feature explicitly reintroduces them.

### Troubleshooting: 502 Bad Gateway on Google login

If `https://empirico.ai/api/v2/auth/google/login` returns **502 Bad Gateway**:

1. **Backend reachable** – Ensure the API container/process is running and nginx can reach it (e.g. `curl http://localhost:8050/api/v2/health` or your upstream URL).
2. **Production env vars** – Set `BACKEND_URL=https://empirico.ai` and `FRONTEND_URL=https://empirico.ai` (no trailing slash). The backend uses `BACKEND_URL` to build the OAuth callback URL.
3. **Google OAuth** – Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and optionally `GOOGLE_REDIRECT_URI=https://empirico.ai/api/v2/auth/google/callback` in the backend environment.
4. **Logs** – Check backend logs when you hit the login URL; errors are logged with traceback.

### Google OAuth Setup

1. **Configure OAuth**
   - Create OAuth 2.0 Client IDs (Web and Android)
   - Add authorized redirect URIs
   - Configure Android OAuth client with package name and SHA-1

---

## 📚 API Documentation

### Base URL
```
Production: https://empirico.ai/api/v2/
Development: http://localhost:8050/api/v2/
```

### Interactive API Documentation
- **Swagger UI**: `/api/v2/docs`
- **ReDoc**: `/api/v2/redoc`

### Key Endpoints

#### Authentication
- `POST /auth/register` - Register new user
- `POST /auth/login` - User login
- `POST /auth/google-sign-in-mobile` - Google Sign-In (mobile)
- `GET /auth/me` - Get current user profile
- `POST /auth/refresh` - Refresh access token

#### Clinical Chat
- `POST /diagnosis/diagnose` - Generate AI medical information response
- `POST /diagnosis/diagnose/stream` - Streamed AI responses
- `POST /diagnosis/feedback` - Submit message feedback
- `GET /chat/sessions` - List chat sessions
- `POST /chat/sessions` - Create new session
- `GET /chat/sessions/{id}/messages` - Get session messages

#### Admin
- `GET /admin/metrics` - Get system metrics
- `GET /admin/metrics/devices` - Get device statistics
- `GET /admin/users` - List users

#### Health
- `GET /health` - Health check endpoint

---

## 📱 Platforms

### Web Application
- **URL**: https://empirico.ai
- **Features**: Full-featured web interface with all capabilities
- **Browser Support**: Modern browsers (Chrome, Firefox, Safari, Edge)

### Android Mobile App
- **Package**: `ai.empirico.app`
- **Minimum SDK**: Android 8.0 (API 26)
- **Target SDK**: Android 14+ (API 36)
- **Download**: Available on Google Play Store
- **Features**: 
  - Offline-capable chat interface
  - Session management
  - Google Sign-In integration
  - AI response formatting consistent with web app (headings, spacing, lists, blockquotes)
  - Push notifications (coming soon)
- **Release builds**: For Google Sign-In to work in release APKs, add your **release keystore SHA-1** to the Android OAuth client in Google Cloud Console (APIs & Services → Credentials → your Android OAuth 2.0 client).

---

## 🔒 Security & Compliance

### Security Features

- **Authentication**: JWT tokens with secure refresh mechanism
- **Authorization**: Role-based access control (RBAC)
- **Data Encryption**: AES-256 encryption for sensitive data
- **Input Validation**: Comprehensive input sanitization
- **Rate Limiting**: Protection against abuse
- **Audit Logging**: Complete audit trail for compliance
- **PHI Protection**: Automatic PHI detection and sanitization in logs

### Compliance Standards

- **HIPAA**: Healthcare data protection and privacy
- **GDPR**: European data protection regulation compliance
- **ISO 13485**: Medical device software quality management
- **SOC 2 Type II**: Security and availability controls

### Security Best Practices

1. **Always use HTTPS** in production
2. **Store secrets securely** using environment variables or secrets management
3. **Regular security updates** for dependencies
4. **Monitor audit logs** for suspicious activity
5. **Implement network security** (firewalls, VPCs)

---

## 💻 Development

### Repository Structure

```
empirico/
├── backend/                 # FastAPI backend
│   ├── src/healthnavi/     # Main application code
│   │   ├── api/v1/         # API endpoints
│   │   ├── core/           # Core utilities
│   │   ├── models/         # Database models
│   │   ├── services/       # Business logic
│   │   └── schemas/        # Pydantic schemas
│   ├── alembic/            # Database migrations
│   ├── scripts/            # Utility scripts
│   └── tests/              # Test suite
├── frontend/                # React web application
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── pages/          # Page components
│   │   ├── services/       # API clients
│   │   └── styles/         # CSS/styles
│   └── public/             # Static assets
├── mobile/                  # Android mobile app
│   └── app/
│       └── src/main/java/ai/empirico/app/
│           ├── data/       # Data layer
│           ├── ui/         # UI layer
│           └── navigation/ # Navigation
├── docker-compose.yml       # Docker orchestration
└── README.md               # This file
```

### Code Quality

```bash
# Format code
black backend/src/healthnavi
isort backend/src/healthnavi

# Lint code
flake8 backend/src/healthnavi
mypy backend/src/healthnavi

# Security scan
bandit -r backend/src/healthnavi
safety check
```

### Pre-commit Hooks

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

---

## 🧪 Testing

### Backend Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=healthnavi --cov-report=html

# Run specific test categories
pytest -m unit
pytest -m integration
pytest -m security
```

### Frontend Tests

```bash
cd frontend
npm test
npm run test:coverage
```

### Mobile Tests

```bash
cd mobile
./gradlew test
./gradlew connectedAndroidTest
```

---

## 🤝 Contributing

We welcome contributions! Please follow these guidelines:

1. **Fork the repository**
2. **Create a feature branch** (`git checkout -b feature/amazing-feature`)
3. **Make your changes** following our coding standards
4. **Write tests** for new functionality
5. **Update documentation** as needed
6. **Commit your changes** (`git commit -m 'Add amazing feature'`)
7. **Push to the branch** (`git push origin feature/amazing-feature`)
8. **Open a Pull Request**

### Development Guidelines

- Follow PEP 8 for Python code
- Use TypeScript for frontend code
- Follow Kotlin coding conventions for mobile
- Write comprehensive tests
- Update documentation
- Ensure security best practices

---

## 📊 Monitoring & Logging

### Logging

- **Structured Logging**: JSON-formatted logs for easy parsing
- **PHI Sanitization**: Automatic removal of PHI from logs
- **Log Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Audit Logging**: Complete audit trail for compliance

### Monitoring

- **Health Checks**: `/api/v2/health` endpoint
- **Performance Metrics**: Response times, throughput
- **Error Tracking**: Error rates and patterns
- **Security Metrics**: Failed logins, suspicious activity

---

## 🆘 Support

### Documentation

- **API Documentation**: Interactive docs at `/api/v2/docs` (Swagger) and `/api/v2/redoc` (ReDoc). Architecture and security overview are in the [Architecture](#-architecture) and [Security & Compliance](#-security--compliance) sections above.

### Getting Help

- **Issues**: Report bugs or request features via [GitHub Issues](https://github.com/your-org/empirico/issues)
- **Discussions**: Join discussions in [GitHub Discussions](https://github.com/your-org/empirico/discussions)
- **Email**: support@empirico.ai

### Security Issues

For security vulnerabilities, please email **security@empirico.ai** instead of using the public issue tracker.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## ⚠️ Important Disclaimers

**Medical Information Base Disclaimer**: Empirico is a medical information base designed to provide healthcare professionals with evidence-based medical information. It is not intended to replace clinical judgment or serve as a substitute for professional medical advice, diagnosis, or treatment. Always verify information and consult with qualified healthcare professionals for medical decisions.

**Regulatory Compliance**: Users are responsible for ensuring compliance with all applicable healthcare regulations, including HIPAA, GDPR, and local medical device regulations in their jurisdiction.

**Data Privacy**: Empirico handles sensitive medical information. Users must ensure proper data protection measures are in place and comply with all applicable privacy laws.

---

## 🙏 Acknowledgments

- **Empirico Model Service** for evidence retrieval and answer generation
- **FastAPI** for the excellent web framework
- **React** and **Jetpack Compose** communities

---

<div align="center">

**Built with ❤️ for healthcare professionals**

[Website](https://empirico.ai) • [Documentation](https://docs.empirico.ai) • [Support](mailto:support@empirico.ai)

</div>
