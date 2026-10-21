import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Building2, CheckCircle2, Circle, MessageSquareText, PlugZap } from 'lucide-react'
import { Alert, Badge, Card, CardBody, CardHeader, DataTable, EmptyState, ErrorState, LoadingRegion, Skeleton, buttonStyles } from '@/components/ui'
import { useSession } from '@/features/auth/session'
import { fetchInvoices, fetchPayPalStatus, fetchTransactions } from '@/features/paypal/api'
import { formatDateTime, formatMoney } from '@/lib/format'

const STATUS_LABEL: Record<string, string> = {
  S: 'Completed',
  P: 'Pending',
  D: 'Denied',
  V: 'Reversed',
  F: 'Partially refunded',
}

export function DashboardPage() {
  const { me } = useSession()
  const merchant = me?.merchant
  const status = useQuery({ queryKey: ['paypal', 'status'], queryFn: fetchPayPalStatus })
  const txns = useQuery({ queryKey: ['paypal', 'txns'], queryFn: fetchTransactions })
  const invoices = useQuery({ queryKey: ['paypal', 'invoices'], queryFn: fetchInvoices })

  const paypalState = status.data?.state ?? me?.paypal?.state ?? 'not_configured'
  const profileDone = Boolean(merchant?.profile_complete)
  const paypalDone = paypalState === 'connected' || paypalState === 'limited'

  const steps = [
    { key: 'profile', title: 'Complete your business profile', to: '/app/settings', done: profileDone, icon: Building2 },
    { key: 'paypal', title: 'Connect PayPal sandbox', to: '/app/integrations', done: paypalDone, icon: PlugZap },
    { key: 'ask', title: 'Ask the assistant about your records', to: '/app/assistant', done: false, icon: MessageSquareText },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="type-page-title">Dashboard</h1>
        <p className="type-body mt-1 text-muted">
          {merchant?.business_name ? `${merchant.business_name} — records from your PayPal sandbox.` : 'Finish setup to see your own payment activity.'}
        </p>
      </div>

      {me && !me.user.email_verified && (
        <Alert tone="warning" title="Confirm your email address" action={<Link to="/verify-email" className={buttonStyles({ variant: 'secondary', size: 'sm' })}>Confirm</Link>}>
          Email ownership is separate from two-factor authentication.
        </Alert>
      )}

      <Card>
        <CardHeader title="Getting started" description="Financial figures appear only after a verified PayPal sync. Nothing is estimated." />
        <CardBody className="space-y-3">
          {steps.map((step) => (
            <Link key={step.key} to={step.to} className="flex items-center gap-4 rounded-md border border-line px-4 py-3 hover:bg-page">
              {step.done ? <CheckCircle2 className="size-5 text-success" aria-hidden /> : <Circle className="size-5 text-muted" aria-hidden />}
              <div className="min-w-0 flex-1">
                <p className="font-semibold text-ink">{step.title}</p>
                <p className="type-helper">{step.done ? 'Done' : 'Not done yet'}</p>
              </div>
              <step.icon className="size-5 text-muted" aria-hidden />
            </Link>
          ))}
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Recent transactions"
          description="Imported from GET /v1/reporting/transactions. Amounts stay in their source currency."
          action={<Badge tone={paypalState === 'connected' ? 'success' : 'warning'}>{paypalState.replaceAll('_', ' ')}</Badge>}
        />
        {txns.isPending && (
          <CardBody>
            <LoadingRegion>
              <Skeleton className="h-32 w-full" />
            </LoadingRegion>
          </CardBody>
        )}
        {txns.isError && <ErrorState error={txns.error} onRetry={() => void txns.refetch()} />}
        {txns.data && txns.data.results.length === 0 && (
          <EmptyState
            title="No transactions imported"
            description="Run a synchronisation after PayPal credentials are verified. This table will not show sample rows."
            action={<Link to="/app/integrations" className={buttonStyles({ variant: 'primary' })}>Open PayPal connection</Link>}
          />
        )}
        {txns.data && txns.data.results.length > 0 && (
          <DataTable
            caption="Imported PayPal transactions"
            rows={txns.data.results}
            rowKey={(r) => r.id}
            columns={[
              { key: 'when', header: 'Initiated', render: (r) => formatDateTime(r.initiated_at) },
              { key: 'id', header: 'PayPal id', render: (r) => r.source_id },
              {
                key: 'status',
                header: 'Status',
                render: (r) => <Badge tone={r.status === 'S' ? 'success' : r.status === 'P' ? 'warning' : 'neutral'}>{STATUS_LABEL[r.status] ?? r.status}</Badge>,
              },
              {
                key: 'amt',
                header: 'Amount',
                align: 'right',
                render: (r) => <span className="type-money">{formatMoney(r.amount, r.currency)}</span>,
              },
            ]}
          />
        )}
      </Card>

      <Card>
        <CardHeader title="Invoices" description="Imported from GET /v2/invoicing/invoices. Unpaid invoices are not treated as money received." />
        {invoices.isPending && (
          <CardBody>
            <LoadingRegion>
              <Skeleton className="h-24 w-full" />
            </LoadingRegion>
          </CardBody>
        )}
        {invoices.isError && <ErrorState error={invoices.error} onRetry={() => void invoices.refetch()} />}
        {invoices.data && invoices.data.results.length === 0 && (
          <EmptyState title="No invoices imported" description="If Invoicing is enabled on the sandbox app, they will appear here after a sync." />
        )}
        {invoices.data && invoices.data.results.length > 0 && (
          <DataTable
            caption="Imported PayPal invoices"
            rows={invoices.data.results}
            rowKey={(r) => r.id}
            columns={[
              { key: 'num', header: 'Number', render: (r) => r.invoice_number || r.source_id },
              { key: 'status', header: 'Status', render: (r) => <Badge tone={r.status === 'PAID' ? 'success' : 'warning'}>{r.status}</Badge> },
              {
                key: 'amt',
                header: 'Amount',
                align: 'right',
                render: (r) => <span className="type-money">{formatMoney(r.amount, r.currency)}</span>,
              },
              {
                key: 'due',
                header: 'Still due',
                align: 'right',
                render: (r) => <span className="type-money">{formatMoney(r.due_amount, r.currency)}</span>,
              },
            ]}
          />
        )}
      </Card>
    </div>
  )
}
