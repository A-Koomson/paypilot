import type { ReactNode } from 'react'
import { AlertCircle, Inbox, type LucideIcon } from 'lucide-react'
import { Button } from './Button'
import { ApiError } from '@/lib/api'
import { cn } from '@/lib/cn'

interface EmptyStateProps {
  icon?: LucideIcon
  title: string
  description?: ReactNode
  action?: ReactNode
  className?: string
}

export function EmptyState({ icon: Icon = Inbox, title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn('flex flex-col items-center px-6 py-10 text-center', className)}>
      <div className="grid size-12 place-items-center rounded-full bg-teal-soft text-navy">
        <Icon className="size-6" aria-hidden />
      </div>
      <h3 className="type-card-title mt-4">{title}</h3>
      {description && <p className="type-body mt-1 max-w-md text-muted">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

interface ErrorStateProps {
  error?: unknown
  title?: string
  onRetry?: () => void
  className?: string
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return 'Something went wrong.'
}

export function ErrorState({ error, title = 'Something went wrong', onRetry, className }: ErrorStateProps) {
  const requestId = error instanceof ApiError ? error.requestId : undefined
  return (
    <div role="alert" className={cn('flex flex-col items-center px-6 py-10 text-center', className)}>
      <div className="grid size-12 place-items-center rounded-full bg-danger-soft text-danger">
        <AlertCircle className="size-6" aria-hidden />
      </div>
      <h3 className="type-card-title mt-4">{title}</h3>
      <p className="type-body mt-1 max-w-md text-muted">{errorMessage(error)}</p>
      {requestId && <p className="type-helper mt-1">Reference: {requestId}</p>}
      {onRetry && (
        <Button variant="secondary" className="mt-5" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  )
}
