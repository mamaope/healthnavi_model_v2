# Partner Integration Guide — Diagnosis API

This guide describes a secure, scoped way to let a partner system call the diagnosis endpoint via the partner-only path while leaving existing app APIs unchanged.

## Environments
- Sandbox: https://<sandbox-host>/partner/diagnosis/diagnose
- Production: https://<prod-host>/partner/diagnosis/diagnose

## Authentication (recommended)
Prefer server-to-server access with short-lived tokens:
- Issue a partner-specific client ID/secret.
- Token endpoint (gateway or auth provider): POST /oauth2/token with grant_type=client_credentials, scope diagnosis:read.
- Tokens are short-lived (e.g., 15–30 minutes). Rotate client secrets regularly.

Token requirements (partner path):
- Bearer JWT (HS256) signed with your server key.
- Claims: token_type=partner, scope includes diagnosis:read, sub = partner ID.
- TTL ≤ 30 minutes; rotate signing key regularly.

If client-credentials is not yet available, an interim signed JWT with the above claims is acceptable.

## Network & Transport
- Enforce TLS 1.2+.
- Prefer IP allowlisting for the partner’s egress.
- Optional: mTLS on the partner ingress listener.
- Disable CORS for server-to-server paths (not needed).

## Endpoint
- Method: POST
- Path: /partner/diagnosis/diagnose
- Headers:
  - Authorization: Bearer <access_token>
  - Content-Type: application/json
  - Accept: application/json

### Request Body (example)
```json
{
  "patient_data": "47-year-old male with chest pain radiating to arm, onset 1h ago.",
  "chat_history": "",
  "session_id": null,
  "deep_search": false
}
```
- patient_data (string, required): clinical text.
- chat_history (string, optional): prior turns; keep minimal.
- session_id (string|null, optional): session to continue; omit/null to start new.
- deep_search (bool, optional): enable heavier RAG retrieval; default false.

### Successful Response (example)
```json
{
  "success": true,
  "data": {
    "model_response": "<AI response text>",
    "diagnosis_complete": true,
    "updated_chat_history": "Doctor: ...\nAI Assistant: ...",
    "session_id": null,
    "message_id": null,
    "prompt_type": "quick_search",
    "followup_questions": []
  },
  "metadata": {
    "status_code": 200,
    "message": "OK"
  }
}
```

### Error Responses
- 401/403: auth failed/insufficient scope.
- 400: validation error (e.g., missing patient_data).
- 429: rate limit exceeded.
- 5xx: upstream/service error; includes correlation ID if available.

## Rate Limits & Quotas
- Set per-partner limits (e.g., 60 requests/minute burst, 1000/day).
- Return 429 on exceed; include Retry-After header.

## Logging & PHI Handling
- Do not log request bodies. Log minimal metadata: timestamp, partner/client_id, status, latency, correlation ID.
- Ensure payloads are sent over TLS; avoid unnecessary identifiers.
- Encrypt at rest on your side; partner should do the same.

## Operational Guidance
- Provide a sandbox client ID/secret first; promote to prod after validation.
- Monitor: auth failures, 5xx rates, latency, and usage vs. quota.
- Rotate client secrets on a schedule and on suspected compromise.
- Keep a runbook: how to revoke a client, rotate keys, and raise limits temporarily.

## Sample cURL (client credentials flow)
```bash
# 1) Get token
curl -s -X POST https://<auth-host>/oauth2/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=<CLIENT_ID>&client_secret=<CLIENT_SECRET>&scope=diagnosis:read" \
  | jq -r '.access_token' > /tmp/token.txt

# 2) Call diagnosis (partner path)
curl -s -X POST https://<prod-host>/partner/diagnosis/diagnose \
  -H "Authorization: Bearer $(cat /tmp/token.txt)" \
  -H "Content-Type: application/json" \
  -d '{"patient_data":"47-year-old male with chest pain radiating to arm","chat_history":"","session_id":null,"deep_search":false}'
```

## Minimal Requirements Checklist
- [ ] Partner-specific credentials (no shared secrets across partners).
- [ ] Short-lived tokens; rotate client secrets.
- [ ] IP allowlist (or mTLS) for partner traffic.
- [ ] Per-partner rate limits and quotas with 429 handling.
- [ ] No body logging; PHI-safe logging only.
- [ ] TLS enforced; CORS off for server-to-server.
- [ ] Clear sandbox vs. production endpoints and credentials.

