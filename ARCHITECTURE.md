# HealthNavi Architecture & Security Overview

## System Components
- **Clients**: React web app, Android mobile app (Retrofit).
- **Backend**: FastAPI single service exposing `/api/v2/{auth,diagnosis,chat}` with permissive CORS (currently `*`).
- **Data Stores**: Postgres (users, sessions, messages, feedback), Zilliz/Milvus vector DB (retrieval context).
- **AI**: Google Vertex AI / GenAI via initialized client and prompts.

## Key Backend Modules (code-derived)
- `backend/src/healthnavi/main.py`: App setup, CORS, router mounts at `/api/v2/...`, startup init for DB, vector store, GenAI.
- `backend/src/healthnavi/api/v1/auth.py`: Registration/login (JWT HS256), Google OAuth (web/mobile), roles (user/admin/super_admin), user CRUD, password reset.
- `backend/src/healthnavi/api/v1/diagnosis.py`: AI diagnosis endpoint (allows anonymous), feedback endpoints, diagnosis health check.
- `backend/src/healthnavi/api/v1/chat_sessions.py`: Chat session/message CRUD tied to authenticated users.
- Services: `conversational_service` (LLM + RAG), `vectorstore_manager` (Zilliz), `genai_client` (Vertex init), `diagnosis_session_service` (sessions/messages).
- Config: `.env` driven; `core/config.py` validates DB/SECURITY/APP settings.

## API Surface (major paths)
- Auth: `/api/v2/auth/{register,login,me,users,...}`, Google OAuth web `/google/login|callback`, mobile `/google/mobile`.
- Diagnosis: `/api/v2/diagnosis/diagnose`, `/feedback`, `/feedback/{message_id}`, `/health`.
- Chat: `/api/v2/chat/sessions` CRUD, `/sessions/{id}/messages`, `/sessions/{id}/history`.
- App health: `/health`.

## Client Integrations
- **Web (frontend/src/services/apiClient.ts)**: Uses bearer token; calls auth, chat sessions, diagnosis, feedback.
- **Mobile (mobile/.../ApiService.kt)**: Base URL `https://healthnavy.mamaope.com/api/v2/`; same endpoints with bearer token header from `RetrofitClient`.

## Security Findings (priority)
1) Diagnosis endpoint allows anonymous access → AI + vector search exposed to unauthenticated users.
2) CORS set to `*` → token exposure risk across origins.
3) Email verification effectively bypassed (users auto-verified).
4) Password policy enforcement weak at runtime (config min length 4; no complexity on register/reset).
5) Secrets handling: SECRET_KEY/ENCRYPTION_KEY can be auto-generated/logged if missing; risk of key loss/log leakage.
6) OAuth state cookie lacks `Secure`/`SameSite=strict` → CSRF/leakage risk over HTTPS.
7) No rate limiting/lockout applied on auth/diagnosis routes.
8) Logging may capture PHI (request logging, prompt/context logs) despite sanitizer utilities.
9) Vector store init hard-fails startup; no graceful degradation path.
10) Mobile tokens not forcibly cleared on 401/403 (web does).

## Recommendations
- Require auth for `/diagnosis/diagnose` or create a capped, no-PHI demo route with strict rate limits.
- Restrict CORS to env-driven allowlist per environment.
- Re-enable email verification: set `is_email_verified=False` by default; block login until verified; gate registration if email service unavailable.
- Enforce strong password policy (≥12 chars, complexity) in registration/reset; align config defaults.
- Make SECRET_KEY/ENCRYPTION_KEY mandatory; fail fast if absent; remove auto-generation/logging in prod; store in secret manager.
- Harden OAuth cookies: `Secure`, `HttpOnly`, `SameSite=strict`; rotate state; consider server-side storage.
- Add rate limiting/lockout middleware on auth and diagnosis endpoints.
- Sanitize or disable sensitive logging in production; avoid logging PHI and full prompts/contexts.
- Vector store: degrade gracefully if load fails; surface health status without crashing the app.
- Mobile: expose logout/clear-token flow; consider TLS pinning; ensure token refresh/expiry handling.

## Diagram (current state)
```mermaid
flowchart LR
  subgraph Clients
    Web[Web App (React/Vite)]
    Mobile[Mobile App (Android/Retrofit)]
  end

  subgraph API[Backend FastAPI /api/v2]
    Auth[Auth Router\nJWT + Google OAuth]
    Chat[Chat Sessions Router]
    Dx[Diagnosis Router\nAI + RAG]
  end

  subgraph Data
    PG[(Postgres)]
    Vector[(Zilliz / Milvus)]
  end

  subgraph AI
    Vertex[Google Vertex AI / GenAI]
  end

  Web -->|Bearer JWT /auth| Auth
  Web -->|/chat, /diagnosis| Chat
  Web -->|/diagnosis| Dx
  Mobile -->|Bearer JWT /auth| Auth
  Mobile -->|/chat, /diagnosis| Dx

  Auth --> PG
  Chat --> PG
  Dx --> PG
  Dx -->|retrieve context| Vector
  Dx -->|LLM prompt| Vertex
```



