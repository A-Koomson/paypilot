import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Alert, Button, Card, CardBody } from '@/components/ui'
import { ApiError } from '@/lib/api'
import { confirmEmailVerification, requestEmailVerification } from '../api'
import { deliveryMessage } from '../delivery'
import { useSession } from '../session'

export function VerifyEmailPage() {
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const { refresh, me } = useSession()
  const [state, setState] = useState<'idle' | 'working' | 'ok' | 'error'>(token ? 'working' : 'idle')
  const [message, setMessage] = useState('')
  const [seenToken, setSeenToken] = useState(token)
  if (token && seenToken !== token) {
    setSeenToken(token)
    setState('working')
  }

  useEffect(() => {
    if (!token) return
    let cancelled = false
    confirmEmailVerification(token)
      .then(async () => {
        if (cancelled) return
        setState('ok')
        setMessage('Your email address is confirmed.')
        await refresh().catch(() => undefined)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setState('error')
        setMessage(err instanceof ApiError ? err.message : 'This link is invalid or has expired.')
      })
    return () => {
      cancelled = true
    }
  }, [token, refresh])

  const resend = async () => {
    setState('working')
    try {
      const res = await requestEmailVerification()
      setState('ok')
      setMessage(deliveryMessage(res.email?.delivery_mode, res.email?.delivered ?? false))
    } catch (err) {
      setState('error')
      setMessage(err instanceof ApiError ? err.message : 'Could not send a confirmation email.')
    }
  }

  return (
    <Card>
      <CardBody className="space-y-5">
        <div>
          <h1 className="type-page-title">Confirm your email</h1>
          <p className="type-body mt-1 text-muted">This proves you own the address. It is not a second sign-in factor.</p>
        </div>
        {state === 'ok' && <Alert tone="success" title={message} />}
        {state === 'error' && <Alert tone="danger" title={message} />}
        {!token && me && !me.user.email_verified && (
          <Button onClick={() => void resend()} loading={state === 'working'}>
            Send a confirmation email
          </Button>
        )}
        {!token && !me && <Alert tone="info" title="Open the link from your email, or sign in and request a new one." />}
        <p className="type-helper">
          <Link to={me ? '/app' : '/login'} className="font-medium text-brand hover:underline">
            {me ? 'Go to the dashboard' : 'Back to sign-in'}
          </Link>
        </p>
      </CardBody>
    </Card>
  )
}
