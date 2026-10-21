import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { Alert, Button, Card, CardBody, Input, buttonStyles } from '@/components/ui'
import { ApiError } from '@/lib/api'
import { loginWithPassword } from '../api'
import { useSession } from '../session'

const schema = z.object({
  email: z.string().email('Enter a valid email address'),
  password: z.string().min(1, 'Enter your password'),
})
type Form = z.infer<typeof schema>

export function LoginPage() {
  const { applyMe, config } = useSession()
  const navigate = useNavigate()
  const location = useLocation()
  const params = new URLSearchParams(location.search)
  const oauthError = params.get('error')
  const [formError, setFormError] = useState<string | null>(oauthError ? 'Google sign-in was cancelled or failed. You can try again or use email.' : null)
  const form = useForm<Form>({ resolver: zodResolver(schema), defaultValues: { email: '', password: '' } })

  const onSubmit = form.handleSubmit(async (values) => {
    setFormError(null)
    try {
      const res = await loginWithPassword(values)
      if (res.status === 'second_factor_required') {
        navigate('/verify')
        return
      }
      if (res.user) applyMe(res as Parameters<typeof applyMe>[0])
      navigate(res.user?.role === 'super_admin' ? '/app/admin' : '/app', { replace: true })
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : 'Sign-in failed.')
    }
  })

  return (
    <Card>
      <CardBody className="space-y-5">
        <div>
          <h1 className="type-page-title">Sign in</h1>
          <p className="type-body mt-1 text-muted">Use your email and password, a one-time code, or Google if it is enabled.</p>
        </div>
        {formError && <Alert tone="danger" title={formError} />}
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <Input label="Email" type="email" autoComplete="email" error={form.formState.errors.email?.message} {...form.register('email')} />
          <Input label="Password" type="password" autoComplete="current-password" error={form.formState.errors.password?.message} {...form.register('password')} />
          <div className="flex justify-end">
            <Link to="/forgot-password" className="text-sm font-medium text-brand hover:underline">
              Forgot password
            </Link>
          </div>
          <Button type="submit" className="w-full" loading={form.formState.isSubmitting}>
            Sign in
          </Button>
        </form>
        <div className="space-y-2">
          <Link to="/login/code" className={buttonStyles({ variant: 'secondary', className: 'w-full' })}>
            Email me a sign-in code
          </Link>
          {config?.google_enabled && (
            <a href="/api/auth/google/start/" className={buttonStyles({ variant: 'secondary', className: 'w-full' })}>
              Continue with Google
            </a>
          )}
        </div>
        <p className="type-helper text-center">
          New to PayPilot?{' '}
          <Link to="/register" className="font-medium text-brand hover:underline">
            Create an account
          </Link>
        </p>
      </CardBody>
    </Card>
  )
}
