import { useEffect } from 'react'
import { Link, Outlet, useLocation } from 'react-router-dom'
import { Footer } from '@/components/layout/Footer'
import { Header } from '@/components/layout/Header'
import { Container, Logo } from '@/components/ui'
import { useShellState } from '@/app/useShellState'

function useScrollToHash() {
  const { pathname, hash } = useLocation()
  useEffect(() => {
    if (hash) {
      document.getElementById(hash.slice(1))?.scrollIntoView()
    } else {
      window.scrollTo(0, 0)
    }
  }, [pathname, hash])
}

function SkipLink() {
  return (
    <a
      href="#main"
      className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[70] focus:rounded-md focus:bg-surface focus:px-4 focus:py-2 focus:font-semibold focus:text-ink focus:shadow-pop"
    >
      Skip to content
    </a>
  )
}

/** Public pages (landing, legal). Header adapts to the auth state; same footer everywhere. */
export function PublicLayout() {
  useScrollToHash()
  const shell = useShellState()
  return (
    <div className="flex min-h-dvh flex-col">
      <SkipLink />
      <Header user={shell.user} paypal={shell.paypal} onLogout={shell.logout} />
      <main id="main" className="flex-1">
        <Outlet />
      </main>
      <Footer />
    </div>
  )
}

/** Centered card layout for sign-in, registration and recovery flows. */
export function AuthLayout() {
  useScrollToHash()
  return (
    <div className="flex min-h-dvh flex-col">
      <SkipLink />
      <header className="on-dark border-b border-on-navy-line bg-navy-deep">
        <Container className="flex h-16 items-center">
          <Link to="/" aria-label="PayPilot home">
            <Logo onDark />
          </Link>
        </Container>
      </header>
      <main id="main" className="flex flex-1 items-start justify-center px-4 py-8 sm:py-14">
        <div className="w-full max-w-md">
          <Outlet />
        </div>
      </main>
      <Footer />
    </div>
  )
}

/** Authenticated application shell. */
export function AppLayout() {
  useScrollToHash()
  const shell = useShellState()
  return (
    <div className="flex min-h-dvh flex-col">
      <SkipLink />
      <Header user={shell.user} paypal={shell.paypal} onLogout={shell.logout} />
      <main id="main" className="flex-1 py-6 sm:py-8">
        <Container>
          <Outlet />
        </Container>
      </main>
      <Footer />
    </div>
  )
}
