import { apiGet, apiPost } from '@/lib/api'

export interface PayPalStatus {
  state: 'checking' | 'not_configured' | 'not_connected' | 'connected' | 'limited' | 'error'
  environment: string
  last_synced_at: string | null
  last_verified_at?: string | null
  last_error_code?: string | null
  last_error_message?: string | null
  transactions_imported?: number
  invoices_imported?: number
  capabilities?: { transactions?: boolean; invoices?: boolean }
  supported_record_types: { type: string; endpoint: string; available: boolean | undefined }[]
  unsupported_record_types: { type: string; reason: string }[]
}

export interface PayPalTransaction {
  id: string
  source_id: string
  status: string
  event_code: string
  amount: string
  currency: string
  initiated_at: string | null
  payer_email: string
  note: string
}

export interface PayPalInvoice {
  id: string
  source_id: string
  invoice_number: string
  status: string
  amount: string
  due_amount: string
  currency: string
  invoice_date: string | null
  due_date: string | null
  recipient_email: string
}

export const fetchPayPalStatus = () => apiGet<PayPalStatus>('/api/integrations/paypal/')
export const verifyPayPal = () => apiPost<PayPalStatus>('/api/integrations/paypal/verify/')
export const syncPayPal = () =>
  apiPost<{ connection: PayPalStatus; transactions: { stored: number }; invoices: { stored: number }; errors: Record<string, string> }>(
    '/api/integrations/paypal/sync/',
  )
export const fetchTransactions = () =>
  apiGet<{ results: PayPalTransaction[] }>('/api/integrations/paypal/transactions/')
export const fetchInvoices = () => apiGet<{ results: PayPalInvoice[] }>('/api/integrations/paypal/invoices/')
