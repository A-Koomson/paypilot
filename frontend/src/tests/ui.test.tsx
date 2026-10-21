import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { Header } from '@/components/layout/Header'
import { Footer } from '@/components/layout/Footer'
import { Alert, Button, Dialog, Input, DataTable } from '@/components/ui'
import { ApiError } from '@/lib/api'
import { formatMoney } from '@/lib/format'
import { LandingPage } from '@/pages/LandingPage'

const wrap = (ui: React.ReactElement) => render(<MemoryRouter>{ui}</MemoryRouter>)

describe('design system components', () => {
  it('Button shows a busy state and blocks clicks while loading', async () => {
    const onClick = vi.fn()
    render(
      <Button loading onClick={onClick}>
        Save
      </Button>,
    )
    const button = screen.getByRole('button', { name: /save/i })
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
    await userEvent.click(button)
    expect(onClick).not.toHaveBeenCalled()
  })

  it('Input links label, hint and error for assistive tech', () => {
    render(<Input label="Email" error="Enter a valid email" />)
    const input = screen.getByLabelText('Email')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input).toHaveAccessibleDescription('Enter a valid email')
  })

  it('Alert uses an assertive role only for problems', () => {
    const { rerender } = render(<Alert tone="danger" title="Failed" />)
    expect(screen.getByRole('alert')).toBeInTheDocument()
    rerender(<Alert tone="success" title="Saved" />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('Dialog traps Escape, is labelled, and restores focus', async () => {
    const onClose = vi.fn()
    render(
      <Dialog open onClose={onClose} title="Confirm">
        <button>Inside</button>
      </Dialog>,
    )
    expect(screen.getByRole('dialog', { name: 'Confirm' })).toHaveAttribute('aria-modal', 'true')
    await userEvent.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalled()
  })

  it('DataTable is a labelled, scrollable region with column headers', () => {
    render(
      <DataTable
        caption="Recent transactions"
        rows={[{ id: 'a', amount: '10.00' }]}
        rowKey={(r) => r.id}
        columns={[
          { key: 'id', header: 'ID', render: (r) => r.id },
          { key: 'amt', header: 'Amount', align: 'right', render: (r) => r.amount },
        ]}
      />,
    )
    expect(screen.getByRole('region', { name: 'Recent transactions' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Amount' })).toBeInTheDocument()
  })
})

describe('layout', () => {
  it('public header exposes sign-in and a working mobile menu toggle', async () => {
    wrap(<Header user={null} onLogout={() => {}} />)
    const toggle = screen.getByRole('button', { name: /open menu/i })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(toggle)
    expect(screen.getByRole('button', { name: /close menu/i })).toHaveAttribute('aria-expanded', 'true')
    await userEvent.keyboard('{Escape}')
    await waitFor(() => expect(screen.getByRole('button', { name: /open menu/i })).toBeInTheDocument())
  })

  it('authenticated header shows merchant navigation and the PayPal status honestly', () => {
    wrap(
      <Header
        user={{ email: 'a@b.co', fullName: 'Ada Lovelace', role: 'merchant' }}
        paypal={{ state: 'not_configured', environment: 'sandbox' }}
        onLogout={() => {}}
      />,
    )
    expect(screen.getAllByRole('link', { name: 'Assistant' }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('link', { name: 'Recovery' }).length).toBeGreaterThan(0)
    expect(screen.getByRole('link', { name: /paypal not set up/i })).toBeInTheDocument()
    expect(screen.queryByText(/paypal connected/i)).not.toBeInTheDocument()
  })

  it('super administrators do not see merchant navigation', () => {
    wrap(<Header user={{ email: 'root@x.co', fullName: '', role: 'super_admin' }} onLogout={() => {}} />)
    expect(screen.queryByRole('link', { name: 'Assistant' })).not.toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Admin' }).length).toBeGreaterThan(0)
  })

  it('footer carries the independent-product disclaimer and draft legal links', () => {
    wrap(<Footer />)
    expect(screen.getByText(/not affiliated with, endorsed by, or sponsored by PayPal/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /privacy \(draft\)/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /terms \(draft\)/i })).toBeInTheDocument()
  })

  it('landing page labels its example as an illustration and promises no invented figures', () => {
    wrap(<LandingPage />)
    expect(screen.getByText(/not real account data/i)).toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/[$€£]\s?\d/)
    expect(screen.getAllByText(/planned/i).length).toBeGreaterThan(0)
  })
})

describe('lib', () => {
  it('formats money without altering the currency', () => {
    expect(formatMoney('1234.50', 'USD', 'en-US')).toBe('$1,234.50')
    expect(formatMoney('10', 'ZZZ-bad', 'en-US')).toBe('10 ZZZ-bad')
  })

  it('ApiError exposes field errors only for validation errors', () => {
    const v = new ApiError({ status: 400, code: 'validation_error', message: 'x', details: { email: ['Bad email'] } })
    expect(v.fieldErrors).toEqual({ email: 'Bad email' })
    const o = new ApiError({ status: 500, code: 'server_error', message: 'x' })
    expect(o.fieldErrors).toEqual({})
  })
})
