import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Badge, Button, Card, CardBody, CardHeader, DataTable, Dialog, EmptyState, ErrorState, Input, LoadingRegion, Select, Skeleton } from '@/components/ui'
import { ApiError } from '@/lib/api'
import { formatDateTime, formatMoney } from '@/lib/format'
import {
  createOrder,
  fetchException,
  fetchExceptions,
  fetchOrders,
  reopenException,
  resolveException,
  runMatching,
  type ReconException,
} from './api'

const KIND_LABEL: Record<string, string> = {
  payment_unmatched: 'Payment unmatched',
  order_unpaid: 'Order without payment',
  payment_unfulfilled: 'Paid but unfulfilled',
  ambiguous: 'Ambiguous match',
  duplicate: 'Duplicate reference',
  amount_mismatch: 'Amount mismatch',
  currency_mismatch: 'Currency mismatch',
  missing_source: 'Needs manual review',
}

export function ReconciliationPage() {
  const qc = useQueryClient()
  const [status, setStatus] = useState('open')
  const [kind, setKind] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [note, setNote] = useState('')
  const [code, setCode] = useState('not_applicable')
  const [orderForm, setOrderForm] = useState({
    internal_reference: '',
    external_reference: '',
    amount: '',
    currency: 'USD',
    customer_reference: '',
  })

  const orders = useQuery({ queryKey: ['recon', 'orders'], queryFn: fetchOrders })
  const exceptions = useQuery({
    queryKey: ['recon', 'exceptions', status, kind],
    queryFn: () => fetchExceptions({ ...(status ? { status } : {}), ...(kind ? { kind } : {}) }),
  })
  const detail = useQuery({
    queryKey: ['recon', 'exception', selectedId],
    queryFn: () => fetchException(selectedId!),
    enabled: Boolean(selectedId),
  })

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ['recon'] })
  }

  const create = useMutation({
    mutationFn: () => createOrder(orderForm),
    onSuccess: () => {
      setOrderForm({ internal_reference: '', external_reference: '', amount: '', currency: 'USD', customer_reference: '' })
      invalidate()
    },
  })
  const run = useMutation({ mutationFn: runMatching, onSuccess: invalidate })
  const resolve = useMutation({
    mutationFn: () => resolveException(selectedId!, code, note),
    onSuccess: () => {
      setNote('')
      invalidate()
      void qc.invalidateQueries({ queryKey: ['recon', 'exception', selectedId] })
    },
  })
  const reopen = useMutation({
    mutationFn: () => reopenException(selectedId!, note),
    onSuccess: () => {
      setNote('')
      invalidate()
      void qc.invalidateQueries({ queryKey: ['recon', 'exception', selectedId] })
    },
  })

  const selected: ReconException | undefined = detail.data

  return (
    <div className="space-y-6">
      <div>
        <h1 className="type-page-title">Reconciliation</h1>
        <p className="type-body mt-1 text-muted">
          Compare internal orders with imported PayPal records. Uncertain matches stay open. Resolving an exception never changes a PayPal transaction.
        </p>
      </div>

      <Card>
        <CardHeader title="Internal orders" description="There is no external fulfillment integration. These records stay in PayPilot." />
        <CardBody className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <Input label="Internal reference" value={orderForm.internal_reference} onChange={(e) => setOrderForm({ ...orderForm, internal_reference: e.target.value })} />
          <Input label="External / PayPal reference" optional value={orderForm.external_reference} onChange={(e) => setOrderForm({ ...orderForm, external_reference: e.target.value })} />
          <Input label="Amount" value={orderForm.amount} onChange={(e) => setOrderForm({ ...orderForm, amount: e.target.value })} />
          <Input label="Currency" value={orderForm.currency} onChange={(e) => setOrderForm({ ...orderForm, currency: e.target.value.toUpperCase() })} />
          <Input label="Customer reference" optional value={orderForm.customer_reference} onChange={(e) => setOrderForm({ ...orderForm, customer_reference: e.target.value })} />
        </CardBody>
        <CardBody className="flex flex-wrap gap-2">
          <Button onClick={() => create.mutate()} loading={create.isPending} disabled={!orderForm.internal_reference || !orderForm.amount}>
            Add order
          </Button>
          <Button variant="secondary" onClick={() => run.mutate()} loading={run.isPending}>
            Run matching
          </Button>
        </CardBody>
        {create.error instanceof ApiError && <Alert tone="danger" title={create.error.message} />}
        {orders.data && orders.data.results.length > 0 && (
          <DataTable
            caption="Internal orders"
            rows={orders.data.results}
            rowKey={(row) => row.id}
            columns={[
              { key: 'ref', header: 'Internal', render: (row) => row.internal_reference },
              { key: 'ext', header: 'External', render: (row) => row.external_reference || '—' },
              { key: 'amt', header: 'Amount', align: 'right', render: (row) => <span className="type-money">{formatMoney(row.amount, row.currency)}</span> },
              { key: 'ful', header: 'Fulfillment', render: (row) => <Badge>{row.fulfillment_status}</Badge> },
            ]}
          />
        )}
      </Card>

      <Card>
        <CardHeader title="Exceptions" description="Only substantiated inconsistencies are listed. Colour is not the only status signal." />
        <CardBody className="grid gap-3 sm:grid-cols-2">
          <Select label="Status" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All</option>
            <option value="open">Open</option>
            <option value="reopened">Reopened</option>
            <option value="resolved">Resolved</option>
          </Select>
          <Select label="Kind" value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="">All kinds</option>
            {Object.entries(KIND_LABEL).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </CardBody>
        {exceptions.isPending && (
          <CardBody>
            <LoadingRegion>
              <Skeleton className="h-32 w-full" />
            </LoadingRegion>
          </CardBody>
        )}
        {exceptions.isError && <ErrorState error={exceptions.error} onRetry={() => void exceptions.refetch()} />}
        {exceptions.data?.results.length === 0 && (
          <EmptyState title="No exceptions in this filter" description="Add internal orders and run matching, or widen the filters." />
        )}
        {exceptions.data && exceptions.data.results.length > 0 && (
          <DataTable
            caption="Reconciliation exceptions"
            rows={exceptions.data.results}
            rowKey={(row) => row.id}
            onRowClick={(row) => setSelectedId(row.id)}
            columns={[
              { key: 'kind', header: 'Kind', render: (row) => KIND_LABEL[row.kind] ?? row.kind },
              { key: 'sev', header: 'Severity', render: (row) => <Badge tone={row.severity === 'attention' ? 'warning' : 'neutral'}>{row.severity}</Badge> },
              { key: 'status', header: 'Status', render: (row) => <Badge>{row.status}</Badge> },
              { key: 'why', header: 'Why it was flagged', render: (row) => row.explanation },
              { key: 'refs', header: 'Records', render: (row) => [row.order_reference, row.invoice_source_id, row.transaction_source_id].filter(Boolean).join(' · ') || '—' },
            ]}
          />
        )}
      </Card>

      <Dialog
        open={Boolean(selectedId)}
        onClose={() => setSelectedId(null)}
        title="Exception detail"
        className="sm:max-w-2xl"
        footer={
          selected && (
            <>
              {selected.status !== 'resolved' ? (
                <Button onClick={() => resolve.mutate()} loading={resolve.isPending} disabled={!note.trim()}>
                  Record resolution
                </Button>
              ) : (
                <Button variant="secondary" onClick={() => reopen.mutate()} loading={reopen.isPending}>
                  Reopen
                </Button>
              )}
            </>
          )
        }
      >
        {detail.isPending && <Skeleton className="h-24 w-full" />}
        {selected && (
          <div className="space-y-4">
            <p>{selected.explanation}</p>
            <p className="type-helper">
              Outcome: {selected.outcome}. This decision does not rewrite the PayPal payment status.
            </p>
            <ol className="space-y-2">
              {selected.history.map((event) => (
                <li key={event.id} className="rounded-md bg-page px-3 py-2 text-sm">
                  <strong>{event.action}</strong> · {formatDateTime(event.created_at)}
                  {event.resolution_code ? ` · ${event.resolution_code}` : ''}
                  {event.note ? ` — ${event.note}` : ''}
                </li>
              ))}
            </ol>
            {selected.status !== 'resolved' && (
              <>
                <Select label="Resolution" value={code} onChange={(e) => setCode(e.target.value)}>
                  <option value="matched_manually">Matched manually</option>
                  <option value="not_applicable">Not applicable</option>
                  <option value="duplicate_ignored">Duplicate ignored</option>
                  <option value="awaiting_fulfillment">Awaiting fulfillment</option>
                  <option value="awaiting_payment">Awaiting payment</option>
                  <option value="data_accepted">Data accepted as-is</option>
                </Select>
                <Input label="Explanatory note" value={note} onChange={(e) => setNote(e.target.value)} />
              </>
            )}
            {(resolve.error instanceof ApiError || reopen.error instanceof ApiError) && (
              <Alert tone="danger" title={(resolve.error || reopen.error)?.message ?? 'Request failed'} />
            )}
          </div>
        )}
      </Dialog>
    </div>
  )
}
