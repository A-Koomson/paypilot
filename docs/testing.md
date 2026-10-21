# Testing

## Backend

```
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements-dev.txt
pytest
```

`pytest.ini` uses `config.settings.test` (fast hasher, locmem mail/cache, empty PayPal/LLM keys).

Markers:

- `live` — real PayPal or LLM. Skipped unless extra env vars are present.

## Frontend

```
cd frontend
npm install
npm test          # vitest + jsdom
npm run typecheck
npm run lint
```

Node 22.11 workers need `--experimental-require-module` for jsdom 27 (set in `vite.config.ts` `execArgv` and the `test` script).

## What the suite covers

Authentication and lockout, OTP expiry/attempts, CSRF on anonymous POSTs, admin policy, merchant isolation, PayPal success/error/pagination/idempotency, IDOR on transactions, deterministic summaries, forbidden tools, prompt-injection write attempts, conversation isolation, production settings.

## What is not claimed

- The skipped live PayPal test is not a passed sandbox run.
- Playwright (`npm run test:e2e`) is reserved; no e2e suite is checked in yet.
- Responsive checks in this repo are component-level plus manual widths, not a full Percy/Chromatic run.
