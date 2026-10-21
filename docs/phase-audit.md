# Audit: Phases 00–03 (before 04–08)

Inspected the repository on 21 October 2026. Documentation is not treated as proof of implementation.

## What is actually implemented

| Phase | Status | Evidence |
|---|---|---|
| 00 Foundation | Implemented | LICENSE, health, JSON errors, redacting logs, append-only `AuditEvent`, prod fail-fast. Tests in `backend/tests/test_foundation.py`. |
| 01 Auth / merchants | Implemented | Session + CSRF cookies, register/login/OTP/2FA/Google, merchant profile, admin policy. Tests in `backend/tests/test_auth.py`. |
| 02 PayPal read sync | Implemented | Client-credentials token, Transaction Search, Invoicing list. Isolated per PayPilot tenant. Tests in `backend/tests/test_paypal.py`. |
| 03 Read-only assistant | Implemented | Four read tools, decimal totals, forbidden write names, prompt-injection tests in `backend/tests/test_agent.py`. |
| Frontend 00–03 | Implemented | Auth, dashboard tables, integrations, assistant, design tokens (navy/blue/teal). Vitest in `frontend/src/tests`. |
| Deploy | Implemented | Cloudflare Pages + Render + Postgres. Push to `main` deploys frontend (Actions) and backend (Render `autoDeploy`). |

## Real vs mocked

- PayPal HTTP client is real `requests` to `api-m.sandbox.paypal.com` when credentials exist.
- Automated tests mock PayPal with `responses`. One optional `@pytest.mark.live` token check is skipped without live test credentials.
- LLM is a real OpenAI-compatible HTTP client. Tests use a scripted provider.

## Security controls already present

- HTTP-only session + CSRF, lockout, OTP hashing, 2FA policy, merchant isolation via `get_merchant(request)`.
- Audit append-only; secrets redacted in logs.
- No refund, send, or remind client existed at audit time.

## Design tokens to preserve

`frontend/src/styles/index.css`: `--pp-navy` `#0b1220`, `--pp-blue` `#2563eb`, `--pp-teal` `#14b8a6`, light page `#f5f7fb`, white surfaces. Reuse `Header`, `Footer`, `Dialog`, `DataTable`, `Card`.

## Blockers for Phase 04

- No recovery models, queue, approval, or execution path.
- `Dialog` exists but is unused in product pages.
- Official remind API exists: `POST /v2/invoicing/invoices/{invoice_id}/remind` (PayPal Invoicing v2). Success is HTTP 204. Custom subject/note are **not** honoured. Limit: two reminders per invoice per day. Requires Invoicing **readwrite**.
- Shared sandbox app credentials: every merchant syncs the same PayPal app ledger (documented limitation).
- No internal order model (needed for Phase 05).
- Merchant-facing audit API does not exist (admin-only).
- Playwright config/tests are missing.

## Decision for reminder execution

1. **PayPal remind** — verified official write. Records success only on 204. UI discloses that PayPal sends its own email.
2. **Copy draft** — always available. Outcome is `copied`, never counted as sent.
3. **SMTP email** — only when `EMAIL_DELIVERY_MODE=smtp` and the backend reports delivery. Console/disabled is not “sent”.
