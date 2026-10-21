# Architecture

```
Browser (Vite / Vercel)
    same-origin /api  ──rewrite──►  Django API (local / Render)
                                         │
                         PostgreSQL (local Docker / Neon)
                         PayPal REST (sandbox)
                         OpenAI-compatible LLM
```

## Backend (`backend/`)

| App | Responsibility |
|---|---|
| `core` | Errors, health, CSRF session auth, logging, permissions |
| `accounts` | Users, OTP, OAuth, security policy |
| `merchants` | Tenant profile |
| `integrations` | PayPal client, sync, imported records |
| `agent` | Conversations, tool registry, provider, runner |
| `audit` | Append-only sanitised events |

Views call services. Services call clients. The LLM never executes SQL or HTTP itself.

## Frontend (`frontend/`)

- `components/ui` + `components/layout` — design system
- `features/{auth,dashboard,paypal,assistant,settings,admin}`
- `lib/api.ts` — cookies, CSRF, error envelope

## Extension points (not implemented)

Reminders, invoice send, refunds, reconciliation and recovery queues should become new services + audited write tools with explicit approval, not new responsibilities on the current read-only registry.
