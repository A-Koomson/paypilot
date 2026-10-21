import type { ComponentProps } from 'react'
import { cn } from '@/lib/cn'

/** The single page container: consistent gutters and max width across header, body and footer. */
export function Container({ className, ...rest }: ComponentProps<'div'>) {
  return <div className={cn('mx-auto w-full max-w-6xl px-4 sm:px-6 lg:px-8', className)} {...rest} />
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string
  description?: string
  actions?: React.ReactNode
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="type-page-title">{title}</h1>
        {description && <p className="type-body mt-1 max-w-2xl text-muted">{description}</p>}
      </div>
      {actions}
    </div>
  )
}
