import type { HeaderUser } from '@/components/layout/UserMenu'
import type { PayPalPillState } from '@/components/layout/PayPalStatusPill'

export interface ShellState {
  user: HeaderUser | null
  paypal?: { state: PayPalPillState; environment?: string }
  logout: () => void
}
