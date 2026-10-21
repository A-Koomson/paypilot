import type { ReactNode } from 'react'
import { Alert, Container } from '@/components/ui'

function LegalShell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Container className="max-w-3xl py-12">
      <h1 className="type-page-title">{title}</h1>
      <Alert tone="warning" title="Draft — not legal advice" className="mt-5">
        This page is a placeholder written for a hackathon prototype. It has not been reviewed by a lawyer and does not
        name a legal entity, address or contact. Replace it before any real-world use.
      </Alert>
      <div className="type-body mt-6 space-y-4 text-ink/90">{children}</div>
    </Container>
  )
}

export function PrivacyPage() {
  return (
    <LegalShell title="Privacy (draft)">
      <p>
        PayPilot stores the account details you provide (email address, name, business profile) and the PayPal records you
        choose to synchronise (transaction and invoice identifiers, amounts, currencies, statuses and dates).
      </p>
      <p>
        Questions you ask the assistant are stored with your account so you can revisit conversations, and are deleted
        after a configurable retention period. Relevant records and your question are sent to the configured AI provider
        to generate an answer. Review that provider’s data-handling terms before using real data.
      </p>
      <p>PayPilot does not sell data. Credentials and access tokens for PayPal and the AI provider stay on the server.</p>
    </LegalShell>
  )
}

export function TermsPage() {
  return (
    <LegalShell title="Terms (draft)">
      <p>
        PayPilot is an independent, open-source prototype. It is not affiliated with, endorsed by, or sponsored by PayPal.
      </p>
      <p>
        The current build connects to the PayPal sandbox only. It is read-only: it does not send reminders, create
        invoices, move money or issue refunds. Answers are generated from synchronised data and may be incomplete or
        delayed; they are not financial, tax or legal advice.
      </p>
      <p>The software is provided “as is”, without warranty. See the repository licence for details.</p>
    </LegalShell>
  )
}
