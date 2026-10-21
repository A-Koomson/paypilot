# Known limitations

- One PayPal REST app is shared. Every PayPilot merchant that syncs imports that sandbox ledger into an isolated PayPilot workspace. This is not Partner Referrals / Log in with PayPal.
- PayPal reminder emails use PayPal’s default subject and note. Custom draft text is for merchant review and for copy/SMTP only.
- SMTP reminders are only “sent” when `EMAIL_DELIVERY_MODE=smtp` and the backend accepts the message.
- Copying a draft is not a sent reminder and is not counted in `reminders_successfully_sent`.
- A sent reminder is not recovered revenue. Confirmed payments require a later PayPal status of `PAID` or `MARKED_AS_PAID`.
- Internal orders have no external fulfillment system. Merchants enter them in PayPilot.
- Amount and currency similarity never auto-matches an order to a payment.
- Refunds and invoice creation are not implemented.
- Playwright end-to-end tests are not checked in.
- The hackathon YouTube demo (under three minutes) is not produced in this repository.
- Free Render Postgres expires; free web sleeps when idle.
- Live PayPal/LLM credentials are not stored in GitHub. CI uses mocks.
