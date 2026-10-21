import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react'
import { CheckCircle2, Info, X, XCircle } from 'lucide-react'
import { cn } from '@/lib/cn'

type ToastTone = 'success' | 'danger' | 'info'
interface ToastItem {
  id: number
  tone: ToastTone
  title: string
  message?: string
}

interface ToastApi {
  notify: (toast: Omit<ToastItem, 'id'>) => void
}

const ToastContext = createContext<ToastApi | null>(null)

// eslint-disable-next-line react-refresh/only-export-components
export function useToast(): ToastApi {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within <ToastProvider>')
  return ctx
}

const toneStyle: Record<ToastTone, { icon: typeof Info; color: string }> = {
  success: { icon: CheckCircle2, color: 'text-success' },
  danger: { icon: XCircle, color: 'text-danger' },
  info: { icon: Info, color: 'text-info' },
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])
  const nextId = useRef(1)

  const dismiss = useCallback((id: number) => setItems((cur) => cur.filter((t) => t.id !== id)), [])
  const notify = useCallback(
    (toast: Omit<ToastItem, 'id'>) => {
      const id = nextId.current++
      setItems((cur) => [...cur.slice(-3), { ...toast, id }])
      window.setTimeout(() => dismiss(id), toast.tone === 'danger' ? 8000 : 5000)
    },
    [dismiss],
  )
  const api = useMemo(() => ({ notify }), [notify])

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 bottom-0 z-[60] flex flex-col items-center gap-2 p-4 sm:items-end"
      >
        {items.map((t) => {
          const { icon: Icon, color } = toneStyle[t.tone]
          return (
            <div
              key={t.id}
              role={t.tone === 'danger' ? 'alert' : 'status'}
              className={cn(
                'pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-md border border-line bg-surface p-4 shadow-pop',
                'animate-[pp-fade-in_160ms_ease-out]',
              )}
            >
              <Icon className={cn('mt-0.5 size-5 shrink-0', color)} aria-hidden />
              <div className="min-w-0 flex-1 text-sm">
                <p className="font-semibold text-ink">{t.title}</p>
                {t.message && <p className="mt-0.5 text-muted">{t.message}</p>}
              </div>
              <button
                type="button"
                onClick={() => dismiss(t.id)}
                aria-label="Dismiss notification"
                className="-m-2 grid size-9 place-items-center rounded-md text-muted hover:text-ink"
              >
                <X className="size-4" aria-hidden />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}
