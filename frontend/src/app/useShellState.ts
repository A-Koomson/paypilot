import { useSession, paypalPill, toHeaderUser } from '@/features/auth/session'
import type { ShellState } from './shellTypes'

export type { ShellState } from './shellTypes'

export function useShellState(): ShellState {
  const { me, logout } = useSession()
  return {
    user: me ? toHeaderUser(me) : null,
    paypal: paypalPill(me),
    logout: () => {
      void logout()
    },
  }
}
