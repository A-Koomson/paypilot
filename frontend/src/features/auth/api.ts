import { api, apiGet, apiPost, apiPatch } from '@/lib/api'
import type { AuthConfig, MeResponse } from './types'

export const fetchAuthConfig = (signal?: AbortSignal) => apiGet<AuthConfig>('/api/auth/config/', undefined, signal)

export const fetchMe = (signal?: AbortSignal) =>
  api<MeResponse>('/api/auth/me/', { signal, quiet401: true })

export const registerAccount = (body: { email: string; full_name: string; password: string }) =>
  api<MeResponse & { status: string; verification_email: { delivered: boolean; delivery_mode: string } }>(
    '/api/auth/register/',
    { method: 'POST', body, quiet401: true },
  )

export const loginWithPassword = (body: { email: string; password: string }) =>
  api<{ status: string } & Partial<MeResponse> & { email?: { delivered: boolean; delivery_mode: string } }>(
    '/api/auth/login/',
    { method: 'POST', body, quiet401: true },
  )

export const logout = () => apiPost<void>('/api/auth/logout/')

export const requestOtp = (email: string) =>
  apiPost<{ status: string; delivery_mode: string; ttl_seconds: number }>('/api/auth/otp/request/', { email })

export const verifyOtp = (email: string, code: string) =>
  api<MeResponse & { status: string }>('/api/auth/otp/verify/', { method: 'POST', body: { email, code }, quiet401: true })

export const requestSecondFactor = () =>
  apiPost<{ status: string; email: { delivered: boolean; delivery_mode: string } }>('/api/auth/second-factor/request/')

export const verifySecondFactor = (code: string) =>
  api<MeResponse & { status: string }>('/api/auth/second-factor/verify/', {
    method: 'POST',
    body: { code },
    quiet401: true,
  })

export const requestEmailVerification = () =>
  apiPost<{ status: string; email?: { delivered: boolean; delivery_mode: string } }>('/api/auth/verify-email/request/')

export const confirmEmailVerification = (token: string) =>
  apiPost<{ status: string; email: string }>('/api/auth/verify-email/', { token })

export const forgotPassword = (email: string) =>
  apiPost<{ status: string; delivery_mode: string }>('/api/auth/password/forgot/', { email })

export const resetPassword = (body: { uid: string; token: string; new_password: string }) =>
  apiPost<{ status: string }>('/api/auth/password/reset/', body)

export const changePassword = (body: { current_password?: string; new_password: string }) =>
  apiPost<void>('/api/auth/password/change/', body)

export const updateMe = (body: { full_name: string }) => apiPatch<MeResponse>('/api/auth/me/', body)

export const updateMerchant = (body: Record<string, string>) => apiPatch('/api/merchant/profile/', body)

export const fetchSecurityPolicy = () =>
  apiGet<{ require_second_factor: boolean; updated_at: string; updated_by_email: string | null }>(
    '/api/admin/security-policy/',
  )

export const updateSecurityPolicy = (require_second_factor: boolean) =>
  apiPatch<{ require_second_factor: boolean }>('/api/admin/security-policy/', { require_second_factor })

export const fetchAdminUsers = () =>
  apiGet<{ results: Array<{ id: string; email: string; full_name: string; role: string; is_active: boolean; business_name: string; created_at: string }> }>(
    '/api/admin/users/',
  )
