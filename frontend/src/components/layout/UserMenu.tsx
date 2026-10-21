import { useEffect, useId, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronDown, LogOut, Settings } from 'lucide-react'
import { cn } from '@/lib/cn'

export interface HeaderUser {
  email: string
  fullName: string
  role: 'merchant' | 'super_admin'
}

function initials(user: HeaderUser): string {
  const source = user.fullName.trim() || user.email
  const parts = source.split(/[\s@.]+/).filter(Boolean)
  return ((parts[0]?.[0] ?? '?') + (parts[1]?.[0] ?? '')).toUpperCase()
}

export function UserMenu({ user, onLogout }: { user: HeaderUser; onLogout: () => void }) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const menuId = useId()

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent | TouchEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onDown)
    document.addEventListener('touchstart', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('touchstart', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const itemClass = 'flex min-h-11 w-full items-center gap-2 rounded-sm px-3 text-sm text-ink hover:bg-page'

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => setOpen((v) => !v)}
        className="flex min-h-11 items-center gap-2 rounded-full border border-on-navy-line py-1 pr-2.5 pl-1 text-white hover:bg-white/10"
      >
        <span className="grid size-8 place-items-center rounded-full bg-teal text-xs font-bold text-navy">
          {initials(user)}
        </span>
        <span className="sr-only">Account menu for {user.email}</span>
        <ChevronDown className={cn('size-4 transition-transform', open && 'rotate-180')} aria-hidden />
      </button>
      {open && (
        <div
          id={menuId}
          role="menu"
          className="absolute right-0 z-40 mt-2 w-64 rounded-md border border-line bg-surface p-1.5 text-ink shadow-pop"
        >
          <div className="border-b border-line px-3 py-2">
            <p className="truncate text-sm font-semibold">{user.fullName || 'Your account'}</p>
            <p className="type-helper truncate">{user.email}</p>
            <p className="type-helper mt-0.5">{user.role === 'super_admin' ? 'Super administrator' : 'Merchant'}</p>
          </div>
          <Link role="menuitem" to="/app/settings" className={itemClass} onClick={() => setOpen(false)}>
            <Settings className="size-4 text-muted" aria-hidden /> Settings
          </Link>
          <button
            role="menuitem"
            type="button"
            className={itemClass}
            onClick={() => {
              setOpen(false)
              onLogout()
            }}
          >
            <LogOut className="size-4 text-muted" aria-hidden /> Log out
          </button>
        </div>
      )}
    </div>
  )
}
