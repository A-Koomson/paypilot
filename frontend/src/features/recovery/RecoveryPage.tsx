import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Badge, Button, Card, CardBody, CardHeader, DataTable, Dialog, EmptyState, ErrorState, LoadingRegion, Select, Skeleton } from '@/components/ui'
import { ApiError } from '@/lib/api'
import { formatDate, formatMoney, formatRelative } from '@/lib/format'
import {
  approveReminder,
  draftReminder,
  executeReminder,
  fetchRecoveryQueue,
  rejectReminder,
  submitReminder,
  type RecoveryAction,
  type RecoveryCase,
} from './api'

function moneyList(rows: { amount: string; currency: string }[]) {
  if (!rows.length) return 'None'
  return rows.map((row) => formatMoney(row.amount, row.currency)).join(' · ')
}

function statusTone(status: string) {
  if (status === 'action_completed' || status === 'resolved') return 'success' as const
  if (status === 'failed') return 'danger' as const
  if (status === 'awaiting_approval' || status === 'approved') return 'warning' as const
  return 'neutral' as const
}

export function RecoveryPage() {
  const qc = useQueryClient()
  const [status, setStatus] = useState('')
  const [currency, setCurrency] = useState('')
  const [sort, setSort] = useState('priority')
  const [selected, setSelected] = useState<RecoveryCase | null>(null)
  const [draft, setDraft] = useState<RecoveryAction | null>(null)
  const [delivery, setDelivery] = useState<RecoveryAction['delivery']>('copy')
  const [result, setResult] = useState<RecoveryAction | null>(null)

  const queue = useQuery({
    queryKey: ['recovery', status, currency, sort],
    queryFn: () => fetchRecoveryQueue({ ...(status ? { status } : {}), ...(currency ? { currency } : {}), sort }),
  })

  const currencies = useMemo(() => {
    const set = new Set(queue.data?.results.map((row) => row.currency) ?? [])
    return [...set].sort()
  }, [queue.data])

  const invalidate = () => void qc.invalidateQueries({ queryKey: ['recovery'] })

  const prepare = useMutation({
    mutationFn: (row: RecoveryCase) => draftReminder(row.id),
    onSuccess: (action, row) => {
      setSelected(row)
      setDraft(action)
      setResult(null)
    },
  })

  const submit = useMutation({
    mutationFn: () => submitReminder(draft!.id, delivery),
    onSuccess: setDraft,
  })

  const approve = useMutation({
    mutationFn: () => approveReminder(draft!.id),
    onSuccess: setDraft,
  })

  const reject = useMutation({
    mutationFn: () => rejectReminder(draft!.id),
    onSuccess: () => {
      setDraft(null)
      setSelected(null)
      invalidate()
    },
  })

  const execute = useMutation({
    mutationFn: async () => {
      if (delivery === 'copy' && draft) await navigator.clipboard.writeText(`${draft.subject}\n\n${draft.body}`)
      return executeReminder(draft!.id, crypto.randomUUID())
    },
    onSuccess: (action) => {
      setResult(action)
      setDraft(action)
      invalidate()
    },
  })

  const error = prepare.error || submit.error || approve.error || execute.error

  return (
    <div className="space-y-6">
      <div>
        <h1 className="type-page-title">Revenue recovery</h1>
        <p className="type-body mt-1 text-muted">
          Outstanding invoices from your imported PayPal records. Totals stay in their source currency. A reminder is never counted as recovered revenue.
        </p>
      </div>

      {queue.data && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Card>
            <CardHeader title="Outstanding identified" />
            <CardBody className="type-money text-ink">{moneyList(queue.data.metrics.outstanding_identified)}</CardBody>
          </Card>
          <Card>
            <CardHeader title="Value with follow-up" />
            <CardBody className="type-money text-ink">{moneyList(queue.data.metrics.value_with_follow_up)}</CardBody>
          </Card>
          <Card>
            <CardHeader title="Reminders sent" description="Delivered by PayPal or SMTP only." />
            <CardBody className="type-money text-ink">{queue.data.metrics.reminders_successfully_sent}</CardBody>
          </Card>
          <Card>
            <CardHeader title="Later confirmed paid" />
            <CardBody className="type-money text-ink">{moneyList(queue.data.metrics.payments_subsequently_confirmed)}</CardBody>
          </Card>
          <Card>
            <CardHeader title="Outstanding resolved" />
            <CardBody className="type-money text-ink">{moneyList(queue.data.metrics.outstanding_resolved)}</CardBody>
          </Card>
          <Card>
            <CardHeader title="Failed actions" />
            <CardBody className="type-money text-ink">{queue.data.metrics.failed_actions}</CardBody>
          </Card>
        </div>
      )}

      <Card>
        <CardHeader
          title="Outstanding queue"
          description="Priority is computed on the server from overdue days, amount, status and follow-up history."
        />
        <CardBody className="grid gap-3 sm:grid-cols-3">
          <Select label="Status" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All workflow states</option>
            <option value="identified">Identified</option>
            <option value="draft_prepared">Draft prepared</option>
            <option value="awaiting_approval">Awaiting approval</option>
            <option value="failed">Failed</option>
            <option value="SENT">PayPal SENT</option>
            <option value="UNPAID">PayPal UNPAID</option>
          </Select>
          <Select label="Currency" value={currency} onChange={(e) => setCurrency(e.target.value)}>
            <option value="">All currencies</option>
            {currencies.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </Select>
          <Select label="Sort" value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="priority">Priority</option>
            <option value="amount">Amount (low to high)</option>
            <option value="-amount">Amount (high to low)</option>
            <option value="due_date">Due date</option>
            <option value="age">Age of balance</option>
            <option value="customer">Customer</option>
            <option value="currency">Currency</option>
          </Select>
        </CardBody>
        {queue.isPending && (
          <CardBody>
            <LoadingRegion>
              <Skeleton className="h-40 w-full" />
            </LoadingRegion>
          </CardBody>
        )}
        {queue.isError && <ErrorState error={queue.error} onRetry={() => void queue.refetch()} />}
        {queue.data?.results.length === 0 && (
          <EmptyState
            title="No outstanding invoices"
            description="Synchronise PayPal invoices that are sent, unpaid or partially paid. This queue will not invent rows."
          />
        )}
        {queue.data && queue.data.results.length > 0 && (
          <DataTable
            caption="Outstanding payment requests"
            rows={queue.data.results}
            rowKey={(row) => row.id}
            onRowClick={(row) => {
              setSelected(row)
              setDraft(row.latest_action)
              setResult(null)
            }}
            columns={[
              { key: 'ref', header: 'Reference', render: (row) => row.invoice_number || row.source_id },
              {
                key: 'customer',
                header: 'Customer',
                render: (row) => row.recipient_email || 'Unavailable',
              },
              { key: 'paypal', header: 'PayPal status', render: (row) => <Badge>{row.status}</Badge> },
              {
                key: 'due',
                header: 'Due',
                render: (row) => (row.due_date_available ? formatDate(row.due_date) : 'Unavailable'),
              },
              {
                key: 'age',
                header: 'Overdue',
                render: (row) => (row.overdue_duration_available ? `${row.days_overdue} days` : 'Unavailable'),
              },
              {
                key: 'amt',
                header: 'Outstanding',
                align: 'right',
                render: (row) => <span className="type-money">{formatMoney(row.due_amount, row.currency)}</span>,
              },
              {
                key: 'wf',
                header: 'Workflow',
                render: (row) => <Badge tone={statusTone(row.workflow_status)}>{row.workflow_status.replaceAll('_', ' ')}</Badge>,
              },
              { key: 'follow', header: 'Last follow-up', render: (row) => formatRelative(row.last_follow_up_at) },
            ]}
          />
        )}
      </Card>

      <Dialog
        open={Boolean(selected)}
        onClose={() => {
          setSelected(null)
          setDraft(null)
          setResult(null)
        }}
        title="Review recovery action"
        description={selected?.priority_explanation}
        className="sm:max-w-2xl"
        footer={
          selected && (
            <>
              <Button variant="secondary" onClick={() => reject.mutate()} disabled={!draft || draft.state !== 'awaiting_approval'}>
                Reject
              </Button>
              {!draft || draft.state === 'rejected' || draft.state === 'action_completed' || draft.state === 'failed' ? (
                <Button onClick={() => prepare.mutate(selected)} loading={prepare.isPending}>
                  Prepare draft
                </Button>
              ) : null}
              {draft?.state === 'draft_prepared' && (
                <Button onClick={() => submit.mutate()} loading={submit.isPending}>
                  Submit for approval
                </Button>
              )}
              {draft?.state === 'awaiting_approval' && (
                <Button onClick={() => approve.mutate()} loading={approve.isPending}>
                  Approve this action
                </Button>
              )}
              {draft?.state === 'approved' && (
                <Button onClick={() => execute.mutate()} loading={execute.isPending}>
                  Execute approved action
                </Button>
              )}
            </>
          )
        }
      >
        {selected && (
          <div className="space-y-4">
            <dl className="grid gap-3 sm:grid-cols-2">
              <div>
                <dt className="type-label">Invoice</dt>
                <dd>{selected.invoice_number || selected.source_id}</dd>
              </div>
              <div>
                <dt className="type-label">Recipient</dt>
                <dd>{selected.recipient_email || 'Unavailable from PayPal'}</dd>
              </div>
              <div>
                <dt className="type-label">Outstanding</dt>
                <dd className="type-money">{formatMoney(selected.due_amount, selected.currency)}</dd>
              </div>
              <div>
                <dt className="type-label">Recommended next action</dt>
                <dd>{selected.recommended_action}</dd>
              </div>
            </dl>
            {draft && (
              <>
                <Select label="Delivery method" value={delivery} onChange={(e) => setDelivery(e.target.value as RecoveryAction['delivery'])} disabled={draft.state !== 'draft_prepared'}>
                  <option value="copy">Copy draft — you send it yourself</option>
                  <option value="email">SMTP email — only if configured</option>
                  <option value="paypal_remind">PayPal official reminder</option>
                </Select>
                <Alert tone="info" title="What this delivery does">
                  {delivery === 'paypal_remind'
                    ? 'PayPal sends its own reminder email. Custom subject and note are not honoured.'
                    : delivery === 'email'
                      ? 'PayPilot sends this exact text only if SMTP accepts it.'
                      : 'PayPilot copies the text. That is not a sent reminder.'}
                </Alert>
                <p className="type-label">Exact message for review</p>
                <p className="font-semibold text-ink">{draft.subject}</p>
                <pre className="overflow-x-auto rounded-md bg-page p-3 text-sm whitespace-pre-wrap">{draft.body}</pre>
              </>
            )}
            {error instanceof ApiError && <Alert tone="danger" title={error.message} />}
            {result && (
              <Alert tone={result.state === 'failed' ? 'danger' : 'success'} title={`Outcome: ${result.outcome ?? result.state}`}>
                {result.outcome_detail}
              </Alert>
            )}
          </div>
        )}
      </Dialog>
    </div>
  )
}
