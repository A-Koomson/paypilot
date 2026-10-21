# Security

## Authentication

- Email + password, emailed OTP, optional Google OAuth (PKCE + server-side state).
- Sessions are HTTP-only cookies (`paypilot_session`). CSRF tokens come from `GET /api/auth/csrf/` and are sent in `X-CSRFToken`. The CSRF cookie is HTTP-only.
- Tokens and OTPs are never stored in `localStorage`.
- OTP values are stored as Django password hashes. Attempt counters are committed before errors are raised.
- Password reset uses Django’s token generator. Forgot-password and OTP-request responses do not reveal whether the email exists.
- Login lockout is cache-backed per email+IP.

## Roles and second factor

- `merchant` and `super_admin` are enforced in permission classes, not in the UI.
- Super administrators can require an emailed second factor for sellers. Policy changes are audited. Email-ownership verification is a separate flag (`email_verified_at`).

## Merchant isolation

Every merchant-owned query filters on the merchant attached to `request.user`. Client-supplied merchant ids are ignored. Tests cover IDOR on profiles, transactions and conversations.

## PayPal and AI secrets

Credentials stay in server environment variables. Access tokens are cached server-side and never returned to the browser. Structured logs redact secret-shaped fields.

## Assistant

- Read tools plus `list_recovery_queue` and `draft_payment_reminder` (draft only). `send_invoice_reminder` and other writes stay forbidden.
- Tool arguments are validated with Pydantic. Result sizes are bounded.
- Record text is treated as untrusted. The system prompt is not the security boundary.
- Conversations are merchant-scoped and retained for `AGENT_CONVERSATION_RETENTION_DAYS`.

## Approvals and idempotency

- Opening a page or sending a chat message is not approval.
- `recovery.execute` requires `confirm=true`, a prior `approved_at`, and an idempotency key.
- Duplicate in-flight reminder actions on the same case are rejected.
- PayPal remind is not retried on timeout; the action is marked `uncertain`, not sent.

## Audit

- Events are append-only. Ordinary merchants can read their own events at `GET /api/audit/` and cannot edit them.
- Metadata is sanitised. Tokens, passwords and OTPs are redacted.

## Production

`config.settings.prod` refuses wildcard hosts/CORS, short or default secret keys, and non-HTTPS frontend origins. Cookies are `Secure`. See `docs/deployment.md`.
