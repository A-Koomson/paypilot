import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Badge, Card, CardBody, CardHeader, DataTable, ErrorState, LoadingRegion, Skeleton } from '@/components/ui'
import { useToast } from '@/components/ui'
import { fetchAdminUsers, fetchSecurityPolicy, updateSecurityPolicy } from '@/features/auth/api'
import { formatDateTime } from '@/lib/format'

export function AdminPage() {
  const { notify } = useToast()
  const qc = useQueryClient()
  const policy = useQuery({ queryKey: ['admin', 'policy'], queryFn: fetchSecurityPolicy })
  const users = useQuery({ queryKey: ['admin', 'users'], queryFn: fetchAdminUsers })
  const toggle = useMutation({
    mutationFn: (next: boolean) => updateSecurityPolicy(next),
    onSuccess: (data) => {
      qc.setQueryData(['admin', 'policy'], data)
      notify({ tone: 'success', title: data.require_second_factor ? 'Second factor is now required for sellers.' : 'Second factor is no longer required.' })
    },
    onError: (err) => notify({ tone: 'danger', title: err instanceof Error ? err.message : 'Could not update the policy.' }),
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="type-page-title">Administration</h1>
        <p className="type-body mt-1 text-muted">Super-administrator controls. Changes are enforced on the server and written to the audit log.</p>
      </div>

      <Card>
        <CardHeader title="Seller second-factor policy" description="When enabled, merchants must complete an emailed code after each password or Google sign-in." />
        <CardBody className="space-y-4">
          {policy.isPending && (
            <LoadingRegion>
              <Skeleton className="h-16 w-full" />
            </LoadingRegion>
          )}
          {policy.isError && <ErrorState error={policy.error} onRetry={() => void policy.refetch()} />}
          {policy.data && (
            <>
              <Alert tone="info" title="This is not email-ownership verification.">
                New accounts still confirm they own their address. The control below is an additional sign-in challenge.
              </Alert>
              <label className="flex cursor-pointer items-start gap-3 rounded-md border border-line px-4 py-3">
                <input
                  type="checkbox"
                  className="mt-1 size-4"
                  checked={policy.data.require_second_factor}
                  disabled={toggle.isPending}
                  onChange={(e) => toggle.mutate(e.target.checked)}
                />
                <span>
                  <span className="font-semibold text-ink">Require a second factor for seller accounts</span>
                  <span className="type-helper mt-0.5 block">
                    Currently {policy.data.require_second_factor ? 'on' : 'off'}
                    {policy.data.updated_by_email ? ` · last changed by ${policy.data.updated_by_email}` : ''}.
                  </span>
                </span>
              </label>
            </>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Accounts" />
        {users.isPending && (
          <CardBody>
            <LoadingRegion>
              <Skeleton className="h-40 w-full" />
            </LoadingRegion>
          </CardBody>
        )}
        {users.isError && <ErrorState error={users.error} onRetry={() => void users.refetch()} />}
        {users.data && (
          <DataTable
            caption="Registered accounts"
            rows={users.data.results}
            rowKey={(r) => r.id}
            columns={[
              { key: 'email', header: 'Email', render: (r) => r.email },
              { key: 'name', header: 'Name', render: (r) => r.full_name || r.business_name || '—' },
              {
                key: 'role',
                header: 'Role',
                render: (r) => <Badge tone={r.role === 'super_admin' ? 'teal' : 'neutral'}>{r.role.replace('_', ' ')}</Badge>,
              },
              { key: 'created', header: 'Created', render: (r) => formatDateTime(r.created_at) },
            ]}
          />
        )}
      </Card>
    </div>
  )
}
