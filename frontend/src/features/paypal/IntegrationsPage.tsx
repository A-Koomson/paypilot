import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Badge, Button, Card, CardBody, CardHeader, EmptyState, ErrorState, LoadingRegion, Skeleton } from '@/components/ui'
import { useToast } from '@/components/ui'
import { useSession } from '@/features/auth/session'
import { formatDateTime, formatRelative } from '@/lib/format'
import { fetchPayPalStatus, syncPayPal, verifyPayPal } from './api'

const tone: Record<string, 'success' | 'warning' | 'danger' | 'neutral'> = {
  connected: 'success',
  limited: 'warning',
  not_configured: 'warning',
  not_connected: 'warning',
  error: 'danger',
}

export function IntegrationsPage() {
  const { refresh } = useSession()
  const { notify } = useToast()
  const qc = useQueryClient()
  const status = useQuery({ queryKey: ['paypal', 'status'], queryFn: fetchPayPalStatus })

  const run = async (kind: 'verify' | 'sync') => {
    const result = kind === 'verify' ? await verifyPayPal() : await syncPayPal()
    await qc.invalidateQueries({ queryKey: ['paypal'] })
    await refresh()
    return result
  }

  const verify = useMutation({
    mutationFn: () => run('verify'),
    onSuccess: () => notify({ tone: 'success', title: 'PayPal credentials were verified.' }),
    onError: (err) => notify({ tone: 'danger', title: err instanceof Error ? err.message : 'Verification failed.' }),
  })
  const sync = useMutation({
    mutationFn: () => run('sync'),
    onSuccess: (res) => {
      if ('connection' in res) {
        notify({
          tone: res.connection.state === 'connected' ? 'success' : 'info',
          title: `Imported ${res.transactions.stored} transactions and ${res.invoices.stored} invoices.`,
        })
      }
    },
    onError: (err) => notify({ tone: 'danger', title: err instanceof Error ? err.message : 'Synchronisation failed.' }),
  })

  const data = status.data

  return (
    <div className="space-y-6">
      <div>
        <h1 className="type-page-title">PayPal connection</h1>
        <p className="type-body mt-1 text-muted">
          Sandbox REST credentials stay on the server. A connection is shown as successful only after PayPal accepts a token request.
        </p>
      </div>

      {status.isPending && (
        <LoadingRegion label="Checking PayPal status">
          <Skeleton className="h-40 w-full" />
        </LoadingRegion>
      )}
      {status.isError && <ErrorState error={status.error} onRetry={() => void status.refetch()} />}

      {data && (
        <>
          <Card>
            <CardHeader
              title="Application credentials"
              description={`${data.environment} environment`}
              action={<Badge tone={tone[data.state] ?? 'neutral'}>{data.state.replaceAll('_', ' ')}</Badge>}
            />
            <CardBody className="space-y-4">
              {data.state === 'not_configured' && (
                <Alert tone="warning" title="PayPal credentials are not configured">
                  Set <code className="rounded bg-page px-1">PAYPAL_CLIENT_ID</code> and{' '}
                  <code className="rounded bg-page px-1">PAYPAL_CLIENT_SECRET</code> on the server for a sandbox REST app
                  with Transaction Search and Invoicing enabled. Then verify.
                </Alert>
              )}
              {data.last_error_message && (
                <Alert tone="danger" title={data.last_error_message}>
                  {data.last_error_code ? `Code: ${data.last_error_code}` : null}
                </Alert>
              )}
              <dl className="grid gap-3 sm:grid-cols-3">
                <div>
                  <dt className="type-label text-muted">Last verified</dt>
                  <dd className="mt-1">{data.last_verified_at ? formatDateTime(data.last_verified_at) : 'Never'}</dd>
                </div>
                <div>
                  <dt className="type-label text-muted">Last synchronisation</dt>
                  <dd className="mt-1">{formatRelative(data.last_synced_at)}</dd>
                </div>
                <div>
                  <dt className="type-label text-muted">Imported records</dt>
                  <dd className="mt-1 tabular">
                    {data.transactions_imported ?? 0} transactions · {data.invoices_imported ?? 0} invoices
                  </dd>
                </div>
              </dl>
              <div className="flex flex-wrap gap-2">
                <Button onClick={() => verify.mutate()} loading={verify.isPending} disabled={data.state === 'not_configured'}>
                  Verify credentials
                </Button>
                <Button variant="secondary" onClick={() => sync.mutate()} loading={sync.isPending} disabled={data.state === 'not_configured'}>
                  Synchronise records
                </Button>
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Supported record types" description="Only endpoints confirmed in PayPal’s current REST documentation." />
            <CardBody className="space-y-3">
              {data.supported_record_types.map((row) => (
                <div key={row.type} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-line px-4 py-3">
                  <div>
                    <p className="font-semibold capitalize">{row.type}</p>
                    <p className="type-helper">{row.endpoint}</p>
                  </div>
                  <Badge tone={row.available ? 'success' : row.available === false ? 'warning' : 'neutral'}>
                    {row.available ? 'verified' : row.available === false ? 'failed last sync' : 'not checked'}
                  </Badge>
                </div>
              ))}
              {data.unsupported_record_types.map((row) => (
                <div key={row.type} className="rounded-md border border-line px-4 py-3">
                  <p className="font-semibold capitalize">{row.type}</p>
                  <p className="type-helper mt-1">{row.reason}</p>
                </div>
              ))}
            </CardBody>
          </Card>
        </>
      )}

      {data?.state === 'not_configured' && (
        <EmptyState title="Nothing to synchronise yet" description="The UI will not invent a successful connection or sample transactions." />
      )}
    </div>
  )
}
