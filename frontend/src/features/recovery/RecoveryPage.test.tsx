import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { RecoveryPage } from './RecoveryPage'

vi.mock('./api', () => ({
  fetchRecoveryQueue: vi.fn(async () => ({
    results: [],
    metrics: {
      outstanding_identified: [],
      value_with_follow_up: [],
      reminders_successfully_sent: 0,
      payments_subsequently_confirmed: [],
      outstanding_resolved: [],
      failed_actions: 0,
      notes: [],
    },
  })),
}))

describe('RecoveryPage', () => {
  it('states that a reminder is not recovered revenue and shows an honest empty queue', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <RecoveryPage />
        </MemoryRouter>
      </QueryClientProvider>,
    )
    expect(await screen.findByText(/never counted as recovered revenue/i)).toBeInTheDocument()
    expect(await screen.findByText(/No outstanding invoices/i)).toBeInTheDocument()
  })
})
