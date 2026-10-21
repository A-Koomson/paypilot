import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, onUnauthenticated, resetCsrfToken } from '@/lib/api'
import type { HeaderUser } from '@/components/layout/UserMenu'
import type { PayPalPillState } from '@/components/layout/PayPalStatusPill'
import { fetchAuthConfig, fetchMe, logout as apiLogout } from './api'
import type { AuthConfig, MeResponse } from './types'

interface Session {
  status: 'loading' | 'anonymous' | 'authenticated'
  me: MeResponse | null
  config: AuthConfig | null
  refresh: () => Promise<MeResponse | null>
  applyMe: (me: MeResponse) => void
  logout: () => Promise<void>
}

const SessionContext = createContext<Session | null>(null)

export function SessionProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Session['status']>('loading')
  const [me, setMe] = useState<MeResponse | null>(null)
  const [config, setConfig] = useState<AuthConfig | null>(null)
  const navigate = useNavigate()

  const applyMe = useCallback((next: MeResponse) => {
    setMe(next)
    setStatus('authenticated')
  }, [])

  const refresh = useCallback(async () => {
    try {
      const next = await fetchMe()
      applyMe(next)
      return next
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setMe(null)
        setStatus('anonymous')
        return null
      }
      throw err
    }
  }, [applyMe])

  const logout = useCallback(async () => {
    try {
      await apiLogout()
    } catch {
      // Session may already be gone.
    }
    resetCsrfToken()
    setMe(null)
    setStatus('anonymous')
    navigate('/login')
  }, [navigate])

  useEffect(() => {
    let cancelled = false
    Promise.all([fetchAuthConfig(), fetchMe().catch((err: unknown) => {
      if (err instanceof ApiError && err.status === 401) return null
      throw err
    })])
      .then(([cfg, session]) => {
        if (cancelled) return
        setConfig(cfg)
        if (session) applyMe(session)
        else setStatus('anonymous')
      })
      .catch(() => {
        if (!cancelled) setStatus('anonymous')
      })
    return () => {
      cancelled = true
    }
  }, [applyMe])

  useEffect(() => onUnauthenticated(() => {
    resetCsrfToken()
    setMe(null)
    setStatus('anonymous')
  }), [])

  const value = useMemo(
    () => ({ status, me, config, refresh, applyMe, logout }),
    [status, me, config, refresh, applyMe, logout],
  )
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export function useSession(): Session {
  const ctx = useContext(SessionContext)
  if (!ctx) throw new Error('useSession must be used within SessionProvider')
  return ctx
}

export function toHeaderUser(me: MeResponse): HeaderUser {
  return { email: me.user.email, fullName: me.user.full_name, role: me.user.role }
}

export function paypalPill(me: MeResponse | null): { state: PayPalPillState; environment?: string } | undefined {
  if (!me?.paypal) return undefined
  return { state: me.paypal.state, environment: me.paypal.environment }
}
