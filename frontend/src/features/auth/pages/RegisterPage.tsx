import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { Alert, Button, Card, CardBody, Input, buttonStyles } from '@/components/ui'
import { ApiError, apiUrl } from '@/lib/api'
import { registerAccount } from '../api'
import { deliveryMessage } from '../delivery'
import { useSession } from '../session'

const schema = z
  .object({
    full_name: z.string().trim().min(2, 'Enter your name'),
    email: z.string().email('Enter a valid email address'),
    password: z.string().min(10, 'Use at least 10 characters'),
    confirm: z.string(),
  })
  .refine((v) => v.password === v.confirm, { path: ['confirm'], message: 'Passwords do not match' })

type Form = z.infer<typeof schema>

export function RegisterPage() {
  const { applyMe, config } = useSession()
  const navigate = useNavigate()
  const [formError, setFormError] = useState<string | null>(null)
  const form = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: { full_name: '', email: '', password: '', confirm: '' },
  })

  const onSubmit = form.handleSubmit(async ({ confirm: _c, ...values }) => {
    setFormError(null)
    try {
      const res = await registerAccount(values)
      applyMe(res)
      navigate(res.second_factor_required ? '/verify' : '/app', {
        replace: true,
        state: { verification: deliveryMessage(res.verification_email.delivery_mode, res.verification_email.delivered) },
      })
    } catch (err) {
      if (err instanceof ApiError && err.code === 'email_in_use') {
        setFormError('An account with this email already exists. Sign in instead.')
        return
      }
      if (err instanceof ApiError && err.code === 'validation_error') {
        for (const [k, v] of Object.entries(err.fieldErrors)) form.setError(k as keyof Form, { message: v })
        return
      }
      setFormError(err instanceof ApiError ? err.message : 'Could not create the account.')
    }
  })

  return (
    <Card>
      <CardBody className="space-y-5">
        <div>
          <h1 className="type-page-title">Create a merchant account</h1>
          <p className="type-body mt-1 text-muted">For the business owner who will connect a PayPal sandbox app.</p>
        </div>
        {formError && <Alert tone="danger" title={formError} />}
        {config?.email_delivery_mode !== 'smtp' && (
          <Alert tone="warning" title="Email delivery is not configured">
            Verification and recovery messages will be printed to the backend console, not delivered to an inbox.
          </Alert>
        )}
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <Input label="Full name" autoComplete="name" error={form.formState.errors.full_name?.message} {...form.register('full_name')} />
          <Input label="Work email" type="email" autoComplete="email" error={form.formState.errors.email?.message} {...form.register('email')} />
          <Input
            label="Password"
            type="password"
            autoComplete="new-password"
            hint="At least 10 characters. Avoid common or leaked passwords."
            error={form.formState.errors.password?.message}
            {...form.register('password')}
          />
          <Input label="Confirm password" type="password" autoComplete="new-password" error={form.formState.errors.confirm?.message} {...form.register('confirm')} />
          <Button type="submit" className="w-full" loading={form.formState.isSubmitting}>
            Create account
          </Button>
        </form>
        {config?.google_enabled && (
          <a href={apiUrl('/api/auth/google/start/')} className={buttonStyles({ variant: 'secondary', className: 'w-full' })}>
            Continue with Google
          </a>
        )}
        <p className="type-helper text-center">
          Already have an account?{' '}
          <Link to="/login" className="font-medium text-brand hover:underline">
            Sign in
          </Link>
        </p>
      </CardBody>
    </Card>
  )
}
