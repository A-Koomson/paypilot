import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { Alert, Button, Card, CardBody, Input } from '@/components/ui'
import { ApiError } from '@/lib/api'
import { forgotPassword } from '../api'
import { deliveryMessage } from '../delivery'

const schema = z.object({ email: z.string().email('Enter a valid email address') })

export function ForgotPasswordPage() {
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema), defaultValues: { email: '' } })

  const onSubmit = form.handleSubmit(async (values) => {
    setError(null)
    try {
      const res = await forgotPassword(values.email)
      setNotice(deliveryMessage(res.delivery_mode, true))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not start password recovery.')
    }
  })

  return (
    <Card>
      <CardBody className="space-y-5">
        <div>
          <h1 className="type-page-title">Reset your password</h1>
          <p className="type-body mt-1 text-muted">We’ll send a link if an account exists for that address. The response is the same either way.</p>
        </div>
        {notice && <Alert tone="info" title={notice} />}
        {error && <Alert tone="danger" title={error} />}
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <Input label="Email" type="email" autoComplete="email" error={form.formState.errors.email?.message} {...form.register('email')} />
          <Button type="submit" className="w-full" loading={form.formState.isSubmitting}>
            Send reset link
          </Button>
        </form>
        <p className="type-helper text-center">
          <Link to="/login" className="font-medium text-brand hover:underline">
            Back to sign-in
          </Link>
        </p>
      </CardBody>
    </Card>
  )
}
