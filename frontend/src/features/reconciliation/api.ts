import { apiGet, apiPost } from '@/lib/api'

export interface InternalOrder {
  id: string
  internal_reference: string
  external_reference: string | null
  amount: string
  currency: string
  status: string
  fulfillment_status: string
  customer_reference: string | null
  created_at: string
}

export interface ReconException {
  id: string
  kind: string
  outcome: string
  status: string
  severity: string
  explanation: string
  transaction_id: string | null
  invoice_id: string | null
  order_id: string | null
  transaction_source_id: string | null
  invoice_source_id: string | null
  order_reference: string | null
  resolution_code: string | null
  resolution_note: string | null
  resolved_at: string | null
  created_at: string
  history: { id: string; action: string; note: string | null; resolution_code: string | null; created_at: string }[]
}

export const fetchOrders = () => apiGet<{ results: InternalOrder[] }>('/api/reconciliation/orders/')
export const createOrder = (body: {
  internal_reference: string
  external_reference?: string
  amount: string
  currency: string
  customer_reference?: string
}) => apiPost<InternalOrder>('/api/reconciliation/orders/', body)
export const runMatching = () => apiPost<{ orders: number; exceptions_open: number }>('/api/reconciliation/run/', {})
export const fetchExceptions = (params?: Record<string, string>) => {
  const query = new URLSearchParams(params)
  const suffix = query.toString() ? `?${query}` : ''
  return apiGet<{ results: ReconException[] }>(`/api/reconciliation/exceptions/${suffix}`)
}
export const fetchException = (id: string) => apiGet<ReconException>(`/api/reconciliation/exceptions/${id}/`)
export const resolveException = (id: string, resolution_code: string, note: string) =>
  apiPost<ReconException>(`/api/reconciliation/exceptions/${id}/resolve/`, { resolution_code, note })
export const reopenException = (id: string, note: string) =>
  apiPost<ReconException>(`/api/reconciliation/exceptions/${id}/reopen/`, { note })
