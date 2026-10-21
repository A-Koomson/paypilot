# PayPal integration

Reviewed against PayPal Developer documentation on 21 October 2026:

- [REST authentication](https://developer.paypal.com/api/rest/authentication)
- [Transaction Search v1](https://developer.paypal.com/docs/api/transaction-search/v1/)
- [Invoicing v2](https://developer.paypal.com/docs/api/invoicing/v2/)
- [Sandbox testing](https://developer.paypal.com/sandbox-testing/overview/)

## Authentication model

PayPilot uses the **application client-credentials** grant (`POST /v1/oauth2/token`) for the REST app whose `PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET` are stored on the server.

That token can only see data belonging to the PayPal account that owns the REST app (typically the developer’s sandbox business account). It does **not** grant access to an arbitrary merchant’s live PayPal account. Third-party merchant onboarding (Partner Referrals / Log in with PayPal) is a future, separately approved flow and is not simulated as complete.

In this prototype every PayPilot merchant that clicks Synchronise imports **that same sandbox app’s** records into their private workspace. Isolation is enforced between PayPilot tenants; it is not a claim that each tenant connected a distinct PayPal identity.

## Hosts

| `PAYPAL_ENVIRONMENT` | Host |
|---|---|
| `sandbox` (default) | `https://api-m.sandbox.paypal.com` |
| `live` | `https://api-m.paypal.com` |

Do not mix sandbox and live credentials. Phase 02/03 are intended for sandbox only.

## Endpoints used

| Purpose | Method | Path | Notes |
|---|---|---|---|
| Access token | `POST` | `/v1/oauth2/token` | `grant_type=client_credentials`, HTTP Basic. |
| Transactions | `GET` | `/v1/reporting/transactions` | Requires the app permission **Transaction Search**. Date window ≤ 31 days; we walk `PAYPAL_SYNC_LOOKBACK_DAYS` in 31-day pages. |
| Invoices (list) | `GET` | `/v2/invoicing/invoices` | Requires **Invoicing**. |
| Invoice (detail) | `GET` | `/v2/invoicing/invoices/{id}` | Implemented on the client; list payload is enough for sync. |
| Invoice reminder | `POST` | `/v2/invoicing/invoices/{id}/remind` | Official write. Success is HTTP 204. Not retried. Custom subject/note are not honoured by PayPal. Limit: two reminders per invoice per day. Requires Invoicing **readwrite**. |

## Endpoints not used (and why)

- **Orders v2** (`/v2/checkout/orders`) — creates and captures checkout orders. It is not a historical activity feed, so `get_orders` is not registered.
- Invoice send / create, refunds, payouts, subscriptions — out of scope. Refunds are not activated.

## Record mapping

Transactions keep PayPal’s `transaction_id`, `transaction_status` (S/P/D/V/…), amount, currency and timestamps. Status **S** is completed; **P** is pending. They are never collapsed.

Invoices keep PayPal’s invoice id, number, status string, amount, due amount and currency. `UNPAID` / `SENT` are not treated as money received.

Repeated sync uses `(merchant, source_id)` uniqueness. Currencies are never converted.

## Sandbox app setup

1. Create a Sandbox REST app at https://developer.paypal.com/dashboard/applications/sandbox
2. Enable **Transaction Search** and **Invoicing**.
3. Put the client id and secret in `.env` (`PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_ENVIRONMENT=sandbox`).
4. Generate sandbox transactions/invoices in the developer dashboard if the account is empty.
5. In PayPilot: Sign in → PayPal → Verify → Synchronise.

Until step 5 succeeds, the UI reports `not_configured` or `not_connected`, never `connected`.

## Tests

`backend/tests/test_paypal.py` mocks PayPal with the `responses` library.

A live token check exists as `test_live_sandbox_token_if_credentials_present` (`@pytest.mark.live`). It is skipped unless `PAYPAL_LIVE_TEST_CLIENT_ID` and `PAYPAL_LIVE_TEST_CLIENT_SECRET` are set. A skipped live test is not a passed integration test.
