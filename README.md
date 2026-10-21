# PayPilot

**Your AI revenue recovery agent.**

PayPilot helps a small business retrieve and understand its **own** PayPal sandbox activity through a natural-language assistant. Figures come from imported records and backend decimal arithmetic — never from the model.

PayPilot is an independent product. It is **not** affiliated with, endorsed by, or sponsored by PayPal.

This repository implements Phases 00–07 of the PayPal AI Hackathon 2026 brief. Invoice creation and refunds are not implemented.

## What works today

- Public landing page and draft legal pages
- Merchant registration, login, logout, email OTP, password recovery, email-ownership verification
- Optional Google OAuth when client id/secret/redirect are set
- Super-administrator second-factor policy for sellers
- PayPal sandbox OAuth, Transaction Search, Invoicing list, official invoice reminder, idempotent sync
- Dashboard, recovery queue, reconciliation exceptions and merchant audit history
- Assistant that can retrieve records and prepare reminder drafts; sending still needs explicit approval
- Deterministic recovery ranking and payment-to-order matching

## What does not work until you add credentials

| Need | Env vars | If missing |
|---|---|---|
| Real email | `EMAIL_HOST` (+ user/password) | Console in development; “nothing sent” in production |
| Google button | `GOOGLE_OAUTH_*` | Button hidden |
| PayPal sync | `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET` | UI shows “not configured” |
| Assistant answers | `LLM_API_KEY`, `LLM_MODEL` | API returns `not_configured` |

Live PayPal verification is **not** claimed in CI. See `docs/paypal-integration.md`.

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up --build
```

- App: http://localhost:5173
- API: http://localhost:8000
- OpenAPI (dev): http://localhost:8000/api/docs/

Default compose Postgres is published on host port `5432` unless you set `POSTGRES_PORT`.

## Quick start (without Compose)

Requires Python 3.11, Node 22.11+, and PostgreSQL.

```bash
cp .env.example .env
# point DATABASE_URL at Postgres

cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py createcachetable
python manage.py runserver

cd ../frontend
npm install
npm run dev
```

Create a super administrator with `python manage.py createsuperuser`.

## Commands

| Area | Command |
|---|---|
| Backend tests | `cd backend && pytest` |
| Backend lint | `cd backend && ruff check .` |
| Frontend tests | `cd frontend && npm test` |
| Frontend types | `cd frontend && npm run typecheck` |
| Frontend lint | `cd frontend && npm run lint` |

## Documentation

- [Architecture](docs/architecture.md)
- [Hackathon compliance](docs/hackathon-compliance.md)
- [PayPal integration](docs/paypal-integration.md)
- [Security](docs/security.md)
- [Testing](docs/testing.md)
- [Deployment](docs/deployment.md)
- [Operations](docs/operations.md)
- [Known limitations](docs/known-limitations.md)
- [Phase 00–03 audit](docs/phase-audit.md)

## Licence

MIT — see `LICENSE`.
