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

- Only four read-only tools are registered. Write names are rejected even if the model asks.
- Tool arguments are validated with Pydantic. Result sizes are bounded.
- Record text is treated as untrusted. The system prompt is not the security boundary.
- Conversations are merchant-scoped and retained for `AGENT_CONVERSATION_RETENTION_DAYS`.

## Production

`config.settings.prod` refuses wildcard hosts/CORS, short or default secret keys, and non-HTTPS frontend origins. Cookies are `Secure`. See `docs/deployment.md`.
