import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

export type Tone = 'neutral' | 'success' | 'warning' | 'danger' | 'info' | 'teal'

const tones: Record<Tone, string> = {
  neutral: 'bg-page text-ink border-line-strong',
  success: 'bg-success-soft text-success border-success/25',
  warning: 'bg-warning-soft text-warning border-warning/25',
  danger: 'bg-danger-soft text-danger border-danger/25',
  info: 'bg-info-soft text-info border-info/25',
  teal: 'bg-teal-soft text-navy border-teal/40',
}

const dots: Record<Tone, string> = {
  neutral: 'bg-muted',
  success: 'bg-success',
  warning: 'bg-warning',
  danger: 'bg-danger',
  info: 'bg-info',
  teal: 'bg-teal',
}

interface BadgeProps {
  tone?: Tone
  children: ReactNode
  dot?: boolean
  className?: string
}

/** Status label. Meaning is always carried by text, never by colour alone. */
export function Badge({ tone = 'neutral', children, dot = true, className }: BadgeProps) {
  return (
    <span
      className={cn(
        'type-status inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 whitespace-nowrap',
        tones[tone],
        className,
      )}
    >
      {dot && <span className={cn('size-1.5 rounded-full', dots[tone])} aria-hidden />}
      {children}
    </span>
  )
}
