import { cn } from '@/lib/cn'

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn(
        'rounded-md bg-line bg-[linear-gradient(90deg,transparent,var(--pp-surface),transparent)] bg-[length:200%_100%]',
        'animate-[pp-shimmer_1.6s_linear_infinite]',
        className,
      )}
    />
  )
}

/** Wraps skeletons with a screen-reader announcement. */
export function LoadingRegion({ label = 'Loading', children }: { label?: string; children: React.ReactNode }) {
  return (
    <div role="status" aria-live="polite" aria-busy="true">
      <span className="sr-only">{label}…</span>
      {children}
    </div>
  )
}
