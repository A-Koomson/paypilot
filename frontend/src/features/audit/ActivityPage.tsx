import { useQuery } from '@tanstack/react-query'
import { Card, CardHeader, DataTable, EmptyState, ErrorState, LoadingRegion, Skeleton } from '@/components/ui'
import { formatDateTime } from '@/lib/format'
import { fetchAudit } from './api'

export function ActivityPage() {
  const audit = useQuery({ queryKey: ['audit'], queryFn: fetchAudit })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="type-page-title">Activity</h1>
        <p className="type-body mt-1 text-muted">
          Append-only events for this merchant. Passwords, tokens and OTPs are never stored here.
        </p>
      </div>
      <Card>
        <CardHeader title="Audit history" description="Ordinary merchants can read their own events but cannot edit or delete them." />
        {audit.isPending && (
          <LoadingRegion>
            <Skeleton className="h-40 w-full" />
          </LoadingRegion>
        )}
        {audit.isError && <ErrorState error={audit.error} onRetry={() => void audit.refetch()} />}
        {audit.data?.results.length === 0 && <EmptyState title="No events yet" description="Approvals, syncs and assistant turns will appear here." />}
        {audit.data && audit.data.results.length > 0 && (
          <DataTable
            caption="Merchant audit events"
            rows={audit.data.results}
            rowKey={(row) => row.id}
            columns={[
              { key: 'when', header: 'When', render: (row) => formatDateTime(row.created_at) },
              { key: 'action', header: 'Action', render: (row) => row.action },
              { key: 'actor', header: 'Actor', render: (row) => row.actor_email || '—' },
              { key: 'target', header: 'Target', render: (row) => [row.target_type, row.target_id].filter(Boolean).join(' ') || '—' },
            ]}
          />
        )}
      </Card>
    </div>
  )
}
