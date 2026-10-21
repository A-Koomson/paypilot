import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { LoadingRegion, Skeleton } from '@/components/ui'
import { useSession } from './session'

function GateSkeleton() {
  return (
    <LoadingRegion label="Checking your session">
      <div className="space-y-3">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-24 w-full" />
      </div>
    </LoadingRegion>
  )
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { status, me } = useSession()
  const location = useLocation()
  if (status === 'loading') return <GateSkeleton />
  if (!me) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (me.second_factor_required && location.pathname !== '/verify') {
    return <Navigate to="/verify" replace />
  }
  return children
}

export function RequireGuest({ children }: { children: ReactNode }) {
  const { status, me } = useSession()
  if (status === 'loading') return <GateSkeleton />
  if (me && me.second_factor_required) return <Navigate to="/verify" replace />
  if (me) return <Navigate to={me.user.role === 'super_admin' ? '/app/admin' : '/app'} replace />
  return children
}

export function RequireMerchant({ children }: { children: ReactNode }) {
  const { me } = useSession()
  if (me?.user.role === 'super_admin') return <Navigate to="/app/admin" replace />
  return children
}

export function RequireAdmin({ children }: { children: ReactNode }) {
  const { me } = useSession()
  if (me?.user.role !== 'super_admin') return <Navigate to="/app" replace />
  return children
}
