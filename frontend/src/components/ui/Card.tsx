import type { ComponentProps, ReactNode } from 'react'
import { cn } from '@/lib/cn'

export function Card({ className, ...rest }: ComponentProps<'section'>) {
  return <section className={cn('rounded-lg border border-line bg-surface shadow-card', className)} {...rest} />
}

interface CardHeaderProps {
  title: ReactNode
  description?: ReactNode
  action?: ReactNode
  as?: 'h2' | 'h3'
  className?: string
}

export function CardHeader({ title, description, action, as: Heading = 'h2', className }: CardHeaderProps) {
  return (
    <div className={cn('flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4', className)}>
      <div className="min-w-0">
        <Heading className="type-card-title text-ink">{title}</Heading>
        {description && <p className="type-helper mt-0.5">{description}</p>}
      </div>
      {action}
    </div>
  )
}

export function CardBody({ className, ...rest }: ComponentProps<'div'>) {
  return <div className={cn('p-5', className)} {...rest} />
}
