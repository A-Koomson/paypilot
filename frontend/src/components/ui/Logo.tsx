import { cn } from '@/lib/cn'

/** PayPilot mark: an original glyph, deliberately unrelated to any payment-network branding. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn('size-8', className)} role="img" aria-label="PayPilot">
      <rect width="32" height="32" rx="8" className="fill-navy-deep stroke-on-navy-line" strokeWidth="1" />
      <path d="M7 17.5 25 8l-6.2 16-3.1-6.3L7 17.5Z" className="fill-teal" />
      <path
        d="m15.7 17.7 9.3-9.7"
        className="stroke-teal-soft"
        strokeWidth="1.6"
        strokeLinecap="round"
        fill="none"
      />
    </svg>
  )
}

export function Logo({ className, onDark = false }: { className?: string; onDark?: boolean }) {
  return (
    <span className={cn('inline-flex items-center gap-2.5', className)}>
      <LogoMark />
      <span className={cn('text-lg font-bold tracking-tight', onDark ? 'text-white' : 'text-ink')}>PayPilot</span>
    </span>
  )
}
