import { useId, type ComponentProps, type ReactNode } from 'react'
import { cn } from '@/lib/cn'

const control =
  'block w-full min-h-11 rounded-md border bg-surface px-3 text-base sm:text-sm text-ink placeholder:text-muted ' +
  'transition-colors focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-brand ' +
  'disabled:bg-page disabled:text-muted'

interface FieldShellProps {
  label: string
  hint?: string
  error?: string
  optional?: boolean
  className?: string
  children: (ids: { id: string; describedBy?: string; invalid: boolean }) => ReactNode
}

/** Label + control + helper/error wiring (aria-describedby, aria-invalid) in one place. */
export function FieldShell({ label, hint, error, optional, className, children }: FieldShellProps) {
  const id = useId()
  const hintId = hint ? `${id}-hint` : undefined
  const errorId = error ? `${id}-error` : undefined
  const describedBy = [errorId, hintId].filter(Boolean).join(' ') || undefined
  return (
    <div className={cn('space-y-1.5', className)}>
      <label htmlFor={id} className="type-label block text-ink">
        {label}
        {optional && <span className="ml-1 font-normal text-muted">(optional)</span>}
      </label>
      {children({ id, describedBy, invalid: Boolean(error) })}
      {hint && !error && (
        <p id={hintId} className="type-helper">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} role="alert" className="type-helper !text-danger">
          {error}
        </p>
      )}
    </div>
  )
}

interface InputProps extends Omit<ComponentProps<'input'>, 'id'> {
  label: string
  hint?: string
  error?: string
  optional?: boolean
  containerClassName?: string
}

export function Input({ label, hint, error, optional, containerClassName, className, ...rest }: InputProps) {
  return (
    <FieldShell label={label} hint={hint} error={error} optional={optional} className={containerClassName}>
      {({ id, describedBy, invalid }) => (
        <input
          id={id}
          aria-invalid={invalid || undefined}
          aria-describedby={describedBy}
          className={cn(control, invalid ? 'border-danger' : 'border-line-strong', className)}
          {...rest}
        />
      )}
    </FieldShell>
  )
}

interface SelectProps extends Omit<ComponentProps<'select'>, 'id'> {
  label: string
  hint?: string
  error?: string
  optional?: boolean
  containerClassName?: string
}

export function Select({ label, hint, error, optional, containerClassName, className, children, ...rest }: SelectProps) {
  return (
    <FieldShell label={label} hint={hint} error={error} optional={optional} className={containerClassName}>
      {({ id, describedBy, invalid }) => (
        <select
          id={id}
          aria-invalid={invalid || undefined}
          aria-describedby={describedBy}
          className={cn(control, 'pr-8', invalid ? 'border-danger' : 'border-line-strong', className)}
          {...rest}
        >
          {children}
        </select>
      )}
    </FieldShell>
  )
}

interface TextareaProps extends Omit<ComponentProps<'textarea'>, 'id'> {
  label: string
  hint?: string
  error?: string
}

export function Textarea({ label, hint, error, className, ...rest }: TextareaProps) {
  return (
    <FieldShell label={label} hint={hint} error={error}>
      {({ id, describedBy, invalid }) => (
        <textarea
          id={id}
          aria-invalid={invalid || undefined}
          aria-describedby={describedBy}
          className={cn(control, 'py-2', invalid ? 'border-danger' : 'border-line-strong', className)}
          {...rest}
        />
      )}
    </FieldShell>
  )
}
