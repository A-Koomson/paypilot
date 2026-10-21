import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { Alert, Button, Card, CardBody, Input } from '@/components/ui'
import { ApiError } from '@/lib/api'
import { requestSecondFactor, verifySecondFactor } from '../api'
import { deliveryMessage } from '../delivery'
import { useSession } from '../session'

const schema = z.object({ code: z.string().regex(/^\d{6}$/, 'Enter the 6-digit code') })

export function SecondFactorPage() {
  const { applyMe, me, status } = useSession()
  const navigate = useNavigate()
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema), defaultValues: { code: '' } })

  useEffect(() => {
    if (status !== 'loading' && me && !me.second_factor_required) {
      navigate(me.user.role === 'super_admin' ? '/app/admin' : '/app', { replace: true })
    }
  }, [me, status, navigate])

  const send = async () => {
    setError(null)
    try {
      const res = await requestSecondFactor()
      setNotice(deliveryMessage(res.email.delivery_mode, res.email.delivered))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not send a code.')
    }
  }

  const onSubmit = form.handleSubmit(async (values) => {
    setError(null)
    try {
      const res = await verifySecondFactor(values.code)
      applyMe(res)
      navigate(res.user.role === 'super_admin' ? '/app/admin' : '/app', { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'That code could not be verified.')
    }
  })

  return (
    <Card>
      <CardBody className="space-y-5">
        <div>
          <h1 className="type-page-title">Confirm it’s you</h1>
          <p className="type-body mt-1 text-muted">
            A super administrator requires an emailed code after sign-in. This is a second factor, not the same as proving
            you own the address when you created the account.
          </p>
        </div>
        {notice && <Alert tone="info" title={notice} />}
        {error && <Alert tone="danger" title={error} />}
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <Input label="6-digit code" inputMode="numeric" autoComplete="one-time-code" error={form.formState.errors.code?.message} {...form.register('code')} />
          <Button type="submit" className="w-full" loading={form.formState.isSubmitting}>
            Continue
          </Button>
        </form>
        <Button variant="secondary" className="w-full" onClick={() => void send()}>
          Email a new code
        </Button>
        <p className="type-helper text-center">
          <Link to="/login" className="font-medium text-brand hover:underline">
            Sign in with a different account
          </Link>
        </p>
      </CardBody>
    </Card>
  )
}
