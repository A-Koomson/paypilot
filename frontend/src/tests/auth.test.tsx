import type { ReactElement } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { LoginPage } from '@/features/auth/pages/LoginPage'
import { SessionProvider } from '@/features/auth/session'
import { deliveryMessage } from '@/features/auth/delivery'

vi.mock('@/features/auth/api', () => ({
  fetchAuthConfig: () => Promise.resolve({ google_enabled: false, email_delivery_mode: 'console', second_factor_required: false, password_min_length: 10, otp_ttl_seconds: 600 }),
  fetchMe: () => Promise.reject({ status: 401, name: 'ApiError' }),
  loginWithPassword: vi.fn(),
  logout: vi.fn(),
}))

function wrap(ui: ReactElement) {
  return render(
    <MemoryRouter>
      <SessionProvider>{ui}</SessionProvider>
    </MemoryRouter>,
  )
}

describe('login page', () => {
  it('blocks submit until a valid email is entered', async () => {
    wrap(<LoginPage />)
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
    expect(await screen.findByText(/valid email/i)).toBeInTheDocument()
  })
})

describe('delivery copy', () => {
  it('never claims an email was sent when delivery is disabled', () => {
    expect(deliveryMessage('disabled', false)).toMatch(/nothing was sent/i)
    expect(deliveryMessage('console', true)).toMatch(/backend console/i)
  })
})
