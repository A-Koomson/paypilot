import { apiGet } from '@/lib/api'

export interface AuditRow {
  id: string
  action: string
  actor_email: string | null
  target_type: string
  target_id: string
  metadata: Record<string, unknown>
  created_at: string
}

export const fetchAudit = () => apiGet<{ results: AuditRow[] }>('/api/audit/')
