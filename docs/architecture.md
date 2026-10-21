# Architecture

```
Browser (Vite / Cloudflare Pages)
    cross-site cookies  ──►  Django API (local / Render)
                                         │
                         PostgreSQL (local Docker / Render)
                         PayPal REST (sandbox)
                         OpenAI-compatible LLM
```

Live hosts: `https://paypilot-dk1.pages.dev` and `https://paypilot-api-tg70.onrender.com`.

## Backend (`backend/`)

| App | Responsibility |
|---|---|
| `core` | Errors, health, CSRF session auth, logging, permissions |
| `accounts` | Users, OTP, OAuth, security policy |
| `merchants` | Tenant profile |
| `integrations` | PayPal client, sync, imported records |
| `agent` | Conversations, tool registry, provider, runner |
| `audit` | Append-only sanitised events (merchant-visible) |
| `policy` | Central authorisation and idempotency keys |
| `recovery` | Outstanding invoice queue, drafts, approval, execution |
| `reconciliation` | Internal orders, matching, exceptions, resolution history |

Views call services. Services call clients. The LLM never executes SQL or HTTP itself. Sending a reminder is a separate approved HTTP action, not a model-invoked write.

## Frontend (`frontend/`)

- `components/ui` + `components/layout` — navy / blue / teal design system
- `features/{auth,dashboard,paypal,assistant,recovery,reconciliation,audit,settings,admin}`
- `lib/api.ts` — cookies, CSRF, error envelope

## Sensitive writes

`apps.policy.authorization.authorize` checks authentication, merchant ownership, supported action, eligibility, amount/currency and explicit approval. `IdempotencyKey` prevents replay of `recovery.execute`.
