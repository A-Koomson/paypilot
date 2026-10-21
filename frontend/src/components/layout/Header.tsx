import { useEffect, useState } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import { LayoutDashboard, LogOut, Menu, MessageSquareText, PlugZap, Settings, ShieldCheck, X } from 'lucide-react'
import { Container, Logo, buttonStyles } from '@/components/ui'
import { cn } from '@/lib/cn'
import { PayPalStatusPill, type PayPalPillState } from './PayPalStatusPill'
import { UserMenu, type HeaderUser } from './UserMenu'

interface NavItem {
  to: string
  label: string
  icon: typeof LayoutDashboard
}

function appNav(user: HeaderUser): NavItem[] {
  if (user.role === 'super_admin') {
    return [{ to: '/app/admin', label: 'Admin', icon: ShieldCheck }]
  }
  return [
    { to: '/app', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/app/assistant', label: 'Assistant', icon: MessageSquareText },
    { to: '/app/integrations', label: 'PayPal', icon: PlugZap },
  ]
}

const publicNav = [
  { href: '/#how-it-works', label: 'How it works' },
  { href: '/#capabilities', label: 'Capabilities' },
  { href: '/#roadmap', label: 'Roadmap' },
]

interface HeaderProps {
  user: HeaderUser | null
  paypal?: { state: PayPalPillState; environment?: string }
  onLogout: () => void
}

export function Header({ user, paypal, onLogout }: HeaderProps) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const { pathname } = useLocation()

  // Close the mobile panel on navigation (derived during render, no effect needed) and with Escape.
  const [lastPath, setLastPath] = useState(pathname)
  if (lastPath !== pathname) {
    setLastPath(pathname)
    setMobileOpen(false)
  }
  useEffect(() => {
    if (!mobileOpen) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setMobileOpen(false)
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [mobileOpen])

  const items = user ? appNav(user) : []
  const desktopLink = ({ isActive }: { isActive: boolean }) =>
    cn(
      'flex min-h-11 items-center rounded-md px-3 text-sm font-medium transition-colors',
      isActive ? 'bg-white/10 text-white' : 'text-on-navy-muted hover:bg-white/5 hover:text-white',
    )

  return (
    <header className="on-dark sticky top-0 z-40 border-b border-on-navy-line bg-navy-deep text-white">
      <Container className="flex h-16 items-center gap-3">
        <Link to={user ? '/app' : '/'} className="rounded-md" aria-label="PayPilot home">
          <Logo onDark />
        </Link>

        <nav aria-label="Main" className="ml-4 hidden items-center gap-1 md:flex">
          {user
            ? items.map((item) => (
                <NavLink key={item.to} to={item.to} end={item.to === '/app'} className={desktopLink}>
                  {item.label}
                </NavLink>
              ))
            : publicNav.map((item) => (
                <Link
                  key={item.href}
                  to={item.href}
                  className="flex min-h-11 items-center rounded-md px-3 text-sm font-medium text-on-navy-muted hover:bg-white/5 hover:text-white"
                >
                  {item.label}
                </Link>
              ))}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          {user ? (
            <>
              {user.role === 'merchant' && paypal && (
                <PayPalStatusPill state={paypal.state} environment={paypal.environment} className="hidden sm:inline-flex" />
              )}
              <UserMenu user={user} onLogout={onLogout} />
            </>
          ) : (
            <div className="hidden items-center gap-2 sm:flex">
              <Link to="/login" className={buttonStyles({ variant: 'ghost', className: 'text-white hover:bg-white/10' })}>
                Sign in
              </Link>
              <Link to="/register" className={buttonStyles({ variant: 'onDark' })}>
                Get started
              </Link>
            </div>
          )}
          <button
            type="button"
            className="grid size-11 place-items-center rounded-md hover:bg-white/10 md:hidden"
            aria-label={mobileOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={mobileOpen}
            aria-controls="mobile-nav"
            onClick={() => setMobileOpen((v) => !v)}
          >
            {mobileOpen ? <X className="size-6" aria-hidden /> : <Menu className="size-6" aria-hidden />}
          </button>
        </div>
      </Container>

      {mobileOpen && (
        <div id="mobile-nav" className="border-t border-on-navy-line bg-navy-deep md:hidden">
          <Container className="max-h-[calc(100dvh-4rem)] space-y-1 overflow-y-auto py-3">
            {user ? (
              <>
                {user.role === 'merchant' && paypal && (
                  <div className="pb-2">
                    <PayPalStatusPill state={paypal.state} environment={paypal.environment} />
                  </div>
                )}
                {items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === '/app'}
                    className={({ isActive }) =>
                      cn(
                        'flex min-h-12 items-center gap-3 rounded-md px-3 text-base font-medium',
                        isActive ? 'bg-white/10 text-white' : 'text-on-navy-muted active:bg-white/5',
                      )
                    }
                  >
                    <item.icon className="size-5" aria-hidden /> {item.label}
                  </NavLink>
                ))}
                <NavLink
                  to="/app/settings"
                  className="flex min-h-12 items-center gap-3 rounded-md px-3 text-base font-medium text-on-navy-muted active:bg-white/5"
                >
                  <Settings className="size-5" aria-hidden /> Settings
                </NavLink>
                <button
                  type="button"
                  onClick={onLogout}
                  className="flex min-h-12 w-full items-center gap-3 rounded-md px-3 text-left text-base font-medium text-on-navy-muted active:bg-white/5"
                >
                  <LogOut className="size-5" aria-hidden /> Log out
                </button>
              </>
            ) : (
              <>
                {publicNav.map((item) => (
                  <Link
                    key={item.href}
                    to={item.href}
                    className="flex min-h-12 items-center rounded-md px-3 text-base font-medium text-on-navy-muted active:bg-white/5"
                  >
                    {item.label}
                  </Link>
                ))}
                <div className="grid grid-cols-2 gap-2 pt-2">
                  <Link to="/login" className={buttonStyles({ variant: 'secondary' })}>
                    Sign in
                  </Link>
                  <Link to="/register" className={buttonStyles({ variant: 'onDark' })}>
                    Get started
                  </Link>
                </div>
              </>
            )}
          </Container>
        </div>
      )}
    </header>
  )
}
