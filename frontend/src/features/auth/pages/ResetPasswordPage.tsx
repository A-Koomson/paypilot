import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { Alert, Button, Card, CardBody, Input } from '@/components/ui'
import { ApiError } from '@/lib/api'
import { resetPassword } from '../api'

const schema = z
  .object({
    new_password: z.string().min(10, 'Use at least 10 characters'),
    confirm: z.string(),
  })
  .refine((v) => v.new_password === v.confirm, { path: ['confirm'], message: 'Passwords do not match' })

export function ResetPasswordPage() {
  const [params] = useSearchParams()
  const uid = params.get('uid') ?? ''
  const token = params.get('token') ?? ''
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema), defaultValues: { new_password: '', confirm: '' } })

  const onSubmit = form.handleSubmit(async (values) => {
    setError(null)
    try {
      await resetPassword({ uid, token, new_password: values.new_password })
      navigate('/login', { replace: true, state: { reset: true } })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'This link is invalid or has expired.')
    }
  })

  return (
    <Card>
      <CardBody className="space-y-5">
        <div>
          <h1 className="type-page-title">Choose a new password</h1>
          <p className="type-body mt-1 text-muted">Use a unique password of at least 10 characters.</p>
        </div>
        {(!uid || !token) && <Alert tone="danger" title="This reset link is missing required information. Request a new one." />}
        {error && <Alert tone="danger" title={error} />}
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <Input label="New password" type="password" autoComplete="new-password" error={form.formState.errors.new_password?.message} {...form.register('new_password')} />
          <Input label="Confirm password" type="password" autoComplete="new-password" error={form.formState.errors.confirm?.message} {...form.register('confirm')} />
          <Button type="submit" className="w-full" loading={form.formState.isSubmitting} disabled={!uid || !token}>
            Update password
          </Button>
        </form>
        <p className="type-helper text-center">
          <Link to="/forgot-password" className="font-medium text-brand hover:underline">
            Request a new link
          </Link>
        </p>
      </CardBody>
    </Card>
  )
}
