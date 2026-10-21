import type { ReactNode } from 'react'
import { AlertTriangle, CheckCircle2, Info, XCircle } from 'lucide-react'
import { cn } from '@/lib/cn'

type AlertTone = 'info' | 'success' | 'warning' | 'danger'

const styles: Record<AlertTone, { box: string; icon: string; Icon: typeof Info }> = {
  info: { box: 'bg-info-soft border-info/25', icon: 'text-info', Icon: Info },
  success: { box: 'bg-success-soft border-success/25', icon: 'text-success', Icon: CheckCircle2 },
  warning: { box: 'bg-warning-soft border-warning/25', icon: 'text-warning', Icon: AlertTriangle },
  danger: { box: 'bg-danger-soft border-danger/25', icon: 'text-danger', Icon: XCircle },
}

interface AlertProps {
  tone?: AlertTone
  title?: string
  children?: ReactNode
  action?: ReactNode
  className?: string
}

export function Alert({ tone = 'info', title, children, action, className }: AlertProps) {
  const { box, icon, Icon } = styles[tone]
  return (
    <div
      role={tone === 'danger' || tone === 'warning' ? 'alert' : 'status'}
      className={cn('flex gap-3 rounded-md border p-4', box, className)}
    >
      <Icon className={cn('mt-0.5 size-5 shrink-0', icon)} aria-hidden />
      <div className="min-w-0 flex-1 text-sm text-ink">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={cn(title && 'mt-0.5', 'text-ink/85')}>{children}</div>}
        {action && <div className="mt-3">{action}</div>}
      </div>
    </div>
  )
}
