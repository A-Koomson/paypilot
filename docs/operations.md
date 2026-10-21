# Operations

## Health

- Live: `GET /api/health/live/`
- Ready: `GET /api/health/ready/` (database + migrations)

## Migrations

`python manage.py migrate` on API boot (Render Docker start command). New apps: `policy`, `recovery`, `reconciliation`, plus `audit.0002`.

## Logging

JSON to stdout with `RedactingFilter`. Do not expect passwords, tokens or OTPs in logs.

## Email

`EMAIL_DELIVERY_MODE` is `smtp` only when `EMAIL_HOST` is set. Otherwise delivery is disabled and the UI says so. Console mode is not treated as sent to a customer.

## PayPal remind

Requires the sandbox app’s Invoicing **readwrite** scope. A 403 is reported as permission denied, not as a sent reminder.

## Rate limits

Auth, OTP, sync and assistant endpoints are throttled. Recovery execute uses the sync throttle.

## Idle API

Render free web services sleep after about 15 minutes. The first request after idle can take ~30 seconds.
