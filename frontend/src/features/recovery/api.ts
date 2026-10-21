import { apiGet, apiPost } from '@/lib/api'

export interface MoneyAmount {
  amount: string
  currency: string
}

export interface RecoveryAction {
  id: string
  kind: string
  delivery: 'copy' | 'email' | 'paypal_remind'
  state: string
  recipient_email: string | null
  subject: string
  body: string
  invoice_reference: string
  amount: string
  currency: string
  delivery_disclosure: string
  approved_at: string | null
  executed_at: string | null
  outcome: string | null
  outcome_detail: string | null
  paypal_http_status: number | null
  created_at: string
}

export interface RecoveryCase {
  id: string
  invoice_id: string
  source_id: string
  invoice_number: string | null
  status: string
  amount: string
  due_amount: string
  currency: string
  recipient_email: string | null
  recipient_available: boolean
  due_date: string | null
  due_date_available: boolean
  days_overdue: number | null
  overdue_duration_available: boolean
  recommended_action: string
  last_follow_up_at: string | null
  workflow_status: string
  merchant_priority: number
  priority_score: number
  priority_explanation: string
  latest_action: RecoveryAction | null
}

export interface RecoveryMetrics {
  outstanding_identified: MoneyAmount[]
  value_with_follow_up: MoneyAmount[]
  reminders_successfully_sent: number
  payments_subsequently_confirmed: MoneyAmount[]
  outstanding_resolved: MoneyAmount[]
  failed_actions: number
  notes: string[]
}

export const fetchRecoveryQueue = (params?: Record<string, string>) => {
  const query = new URLSearchParams(params)
  const suffix = query.toString() ? `?${query}` : ''
  return apiGet<{ results: RecoveryCase[]; metrics: RecoveryMetrics }>(`/api/recovery/${suffix}`)
}

export const draftReminder = (caseId: string) => apiPost<RecoveryAction>(`/api/recovery/cases/${caseId}/draft/`, {})
export const submitReminder = (actionId: string, delivery: RecoveryAction['delivery']) =>
  apiPost<RecoveryAction>(`/api/recovery/actions/${actionId}/submit/`, { delivery })
export const approveReminder = (actionId: string) =>
  apiPost<RecoveryAction>(`/api/recovery/actions/${actionId}/approve/`, { confirm: true })
export const rejectReminder = (actionId: string) => apiPost<RecoveryAction>(`/api/recovery/actions/${actionId}/reject/`, {})
export const executeReminder = (actionId: string, idempotencyKey: string) =>
  apiPost<RecoveryAction>(`/api/recovery/actions/${actionId}/execute/`, { confirm: true, idempotency_key: idempotencyKey })
