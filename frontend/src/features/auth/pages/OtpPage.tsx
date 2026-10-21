import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { Alert, Button, Card, CardBody, Input } from '@/components/ui'
import { ApiError } from '@/lib/api'
import { requestOtp, verifyOtp } from '../api'
import { deliveryMessage } from '../delivery'
import { useSession } from '../session'

const emailSchema = z.object({ email: z.string().email('Enter a valid email address') })
const codeSchema = z.object({ code: z.string().regex(/^\d{6}$/, 'Enter the 6-digit code') })

export function OtpPage() {
  const { applyMe } = useSession()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const emailForm = useForm<z.infer<typeof emailSchema>>({ resolver: zodResolver(emailSchema), defaultValues: { email: '' } })
  const codeForm = useForm<z.infer<typeof codeSchema>>({ resolver: zodResolver(codeSchema), defaultValues: { code: '' } })

  const send = emailForm.handleSubmit(async (values) => {
    setError(null)
    try {
      const res = await requestOtp(values.email)
      setEmail(values.email)
      setNotice(deliveryMessage(res.delivery_mode, true))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not send a code.')
    }
  })

  const verify = codeForm.handleSubmit(async (values) => {
    setError(null)
    try {
      const res = await verifyOtp(email, values.code)
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
          <h1 className="type-page-title">Email sign-in code</h1>
          <p className="type-body mt-1 text-muted">We’ll email a 6-digit code. It expires in a few minutes and has a limited number of attempts.</p>
        </div>
        {notice && <Alert tone="info" title={notice} />}
        {error && <Alert tone="danger" title={error} />}
        {!email ? (
          <form onSubmit={send} className="space-y-4" noValidate>
            <Input label="Email" type="email" autoComplete="email" error={emailForm.formState.errors.email?.message} {...emailForm.register('email')} />
            <Button type="submit" className="w-full" loading={emailForm.formState.isSubmitting}>
              Send code
            </Button>
          </form>
        ) : (
          <form onSubmit={verify} className="space-y-4" noValidate>
            <Input label="6-digit code" inputMode="numeric" autoComplete="one-time-code" error={codeForm.formState.errors.code?.message} {...codeForm.register('code')} />
            <Button type="submit" className="w-full" loading={codeForm.formState.isSubmitting}>
              Verify and sign in
            </Button>
            <Button variant="ghost" className="w-full" onClick={() => setEmail('')}>
              Use a different email
            </Button>
          </form>
        )}
        <p className="type-helper text-center">
          <Link to="/login" className="font-medium text-brand hover:underline">
            Back to password sign-in
          </Link>
        </p>
      </CardBody>
    </Card>
  )
}
