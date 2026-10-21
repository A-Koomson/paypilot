import type { PayPalPillState } from '@/components/layout/PayPalStatusPill'

export interface AuthUser {
  id: string
  email: string
  full_name: string
  role: 'merchant' | 'super_admin'
  email_verified: boolean
  has_password: boolean
  created_at: string
}

export interface MerchantProfile {
  id: string
  business_name: string
  business_type: string
  country: string
  display_currency: string
  timezone: string
  onboarding_status: 'new' | 'profile_complete' | 'paypal_connected' | 'synced'
  profile_complete: boolean
  business_type_options: { value: string; label: string }[]
  created_at: string
  updated_at: string
}

export interface PayPalSummary {
  state: PayPalPillState
  environment: string
  last_synced_at: string | null
}

export interface MeResponse {
  user: AuthUser
  merchant: MerchantProfile | null
  second_factor_required: boolean
  paypal: PayPalSummary | null
}

export interface AuthConfig {
  google_enabled: boolean
  email_delivery_mode: 'smtp' | 'console' | 'disabled'
  second_factor_required: boolean
  password_min_length: number
  otp_ttl_seconds: number
}

export type DeliveryMode = AuthConfig['email_delivery_mode']
