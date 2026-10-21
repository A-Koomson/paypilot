import type { ReactNode } from 'react'
import { Outlet, createBrowserRouter } from 'react-router-dom'
import { AppLayout, AuthLayout, PublicLayout } from '@/layouts/Layouts'
import { LandingPage } from '@/pages/LandingPage'
import { PrivacyPage, TermsPage } from '@/pages/LegalPages'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { SessionProvider } from '@/features/auth/session'
import { RequireAdmin, RequireAuth, RequireGuest, RequireMerchant } from '@/features/auth/gates'
import { LoginPage } from '@/features/auth/pages/LoginPage'
import { RegisterPage } from '@/features/auth/pages/RegisterPage'
import { OtpPage } from '@/features/auth/pages/OtpPage'
import { ForgotPasswordPage } from '@/features/auth/pages/ForgotPasswordPage'
import { ResetPasswordPage } from '@/features/auth/pages/ResetPasswordPage'
import { VerifyEmailPage } from '@/features/auth/pages/VerifyEmailPage'
import { SecondFactorPage } from '@/features/auth/pages/SecondFactorPage'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { SettingsPage } from '@/features/settings/SettingsPage'
import { AdminPage } from '@/features/admin/AdminPage'
import { IntegrationsPage } from '@/features/paypal/IntegrationsPage'
import { AssistantPage } from '@/features/assistant/AssistantPage'
import { RecoveryPage } from '@/features/recovery/RecoveryPage'
import { ReconciliationPage } from '@/features/reconciliation/ReconciliationPage'
import { ActivityPage } from '@/features/audit/ActivityPage'

function Root() {
  return (
    <SessionProvider>
      <Outlet />
    </SessionProvider>
  )
}

function merchant(page: ReactNode) {
  return <RequireMerchant>{page}</RequireMerchant>
}

export const routes = [
  {
    element: <Root />,
    children: [
      {
        element: <PublicLayout />,
        children: [
          { path: '/', element: <LandingPage /> },
          { path: '/privacy', element: <PrivacyPage /> },
          { path: '/terms', element: <TermsPage /> },
        ],
      },
      {
        element: <AuthLayout />,
        children: [
          { path: '/login', element: <RequireGuest><LoginPage /></RequireGuest> },
          { path: '/login/code', element: <RequireGuest><OtpPage /></RequireGuest> },
          { path: '/register', element: <RequireGuest><RegisterPage /></RequireGuest> },
          { path: '/forgot-password', element: <RequireGuest><ForgotPasswordPage /></RequireGuest> },
          { path: '/reset-password', element: <ResetPasswordPage /> },
          { path: '/verify-email', element: <VerifyEmailPage /> },
          { path: '/verify', element: <SecondFactorPage /> },
        ],
      },
      {
        element: (
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        ),
        children: [
          { path: '/app', element: merchant(<DashboardPage />) },
          { path: '/app/recovery', element: merchant(<RecoveryPage />) },
          { path: '/app/reconciliation', element: merchant(<ReconciliationPage />) },
          { path: '/app/activity', element: merchant(<ActivityPage />) },
          { path: '/app/assistant', element: merchant(<AssistantPage />) },
          { path: '/app/integrations', element: merchant(<IntegrationsPage />) },
          { path: '/app/settings', element: <SettingsPage /> },
          { path: '/app/admin', element: <RequireAdmin><AdminPage /></RequireAdmin> },
        ],
      },
      {
        element: <PublicLayout />,
        children: [{ path: '*', element: <NotFoundPage /> }],
      },
    ],
  },
]

export const router = createBrowserRouter(routes)
