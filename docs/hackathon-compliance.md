# Hackathon compliance

Reviewed against the [PayPal AI Hackathon official rules](https://paypalaihackathon.devpost.com/rules) on **21 October 2026**. Recheck before submission; rules can change.

Submission period: 1 Oct 2026 – 12 Nov 2026 (12:00 PT). Judging: 1–15 Dec 2026.

## Required of the project

| Rule | How PayPilot meets it |
|---|---|
| Integrate the PayPal developer platform via the free sandbox | Server-side REST client uses `api-m.sandbox.paypal.com`: OAuth2 client-credentials, Transaction Search, Invoicing v2. See `docs/paypal-integration.md`. |
| Integrate an AI tool, model or platform meaningfully | OpenAI-compatible tool-calling loop. The model selects read-only tools; the backend validates and executes them; totals are computed in Python. |
| Functional application, not a mockup | Django API + React SPA. Judges can run it from the repository (Docker Compose or local venv + Vite). |
| Functions as described in the repo and demo | This file, `README.md` and the other docs state what is implemented and what is not. |
| Authorised third-party APIs / SDKs / assets | PayPal REST, optional Google OAuth, optional OpenAI-compatible LLM (default: Gemini OpenAI-compat endpoint). Inter Variable via Fontsource. MIT-licensed project code. |
| Public repository with a visible open-source license | `LICENSE` is MIT. |
| YouTube demo under three minutes showing the app working | Not produced in this phase; required at submission. |
| Document tools and how they contribute | `README.md` and this file. |

Sponsor AI toolkits are optional. Using one does not guarantee an award. PayPilot does **not** embed `paypal-agent-toolkit`: that toolkit’s default tools include invoice send/remind, order capture and other writes, which Phase 03 forbids. The official REST endpoints it wraps are called through our own client instead.

## Judging criteria (equal weight)

- **Technological implementation** — real sandbox REST calls, session auth, isolated tenants, tool-calling agent.
- **Design** — shared design tokens and components; public + authenticated UI.
- **Potential impact** — small-business payment visibility and an honest assistant.
- **Innovation** — evidence-grounded finance answers with deterministic maths.
- **Presentation** — demo video still required at submission.

## What is deliberately unfinished

Invoice creation and refunds are not implemented. The assistant can draft a reminder but cannot send it; sending is a separate approved action.

Live PayPal sandbox verification is skipped in CI unless `PAYPAL_LIVE_TEST_CLIENT_ID` and `PAYPAL_LIVE_TEST_CLIENT_SECRET` are set. Mocked tests cover the integration. A PayPal remind success is only claimed when the official endpoint returns HTTP 204.

The required YouTube demo (under three minutes) has not been recorded in this repository.
