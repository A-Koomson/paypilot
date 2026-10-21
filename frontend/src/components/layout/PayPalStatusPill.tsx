import { Link } from 'react-router-dom'
import { cn } from '@/lib/cn'

export type PayPalPillState = 'checking' | 'not_configured' | 'not_connected' | 'connected' | 'limited' | 'error'

const labels: Record<PayPalPillState, { text: string; dot: string }> = {
  checking: { text: 'Checking PayPal…', dot: 'bg-on-navy-muted' },
  not_configured: { text: 'PayPal not set up', dot: 'bg-warning' },
  not_connected: { text: 'PayPal not connected', dot: 'bg-warning' },
  connected: { text: 'PayPal connected', dot: 'bg-teal' },
  limited: { text: 'PayPal limited access', dot: 'bg-warning' },
  error: { text: 'PayPal needs attention', dot: 'bg-danger' },
}

interface Props {
  state: PayPalPillState
  environment?: string
  className?: string
}

/** Shows only what the backend has verified; unknown/unchecked states are never rendered as "connected". */
export function PayPalStatusPill({ state, environment, className }: Props) {
  const { text, dot } = labels[state]
  return (
    <Link
      to="/app/integrations"
      className={cn(
        'type-status inline-flex min-h-9 items-center gap-2 rounded-full border border-on-navy-line px-3 text-white',
        'hover:bg-white/10',
        className,
      )}
      aria-label={`${text}${environment ? ` (${environment})` : ''}. Open integration settings.`}
    >
      <span className={cn('size-2 rounded-full', dot)} aria-hidden />
      <span>{text}</span>
      {environment && state !== 'checking' && (
        <span className="rounded bg-white/10 px-1.5 py-0.5 text-[0.6875rem] uppercase tracking-wide">{environment}</span>
      )}
    </Link>
  )
}
