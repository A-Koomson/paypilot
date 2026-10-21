import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { Alert, Button, Card, CardBody, CardHeader, Input, Select } from '@/components/ui'
import { ApiError } from '@/lib/api'
import { useToast } from '@/components/ui'
import { changePassword, requestEmailVerification, updateMe, updateMerchant } from '@/features/auth/api'
import { deliveryMessage } from '@/features/auth/delivery'
import { useSession } from '@/features/auth/session'

const profileSchema = z.object({
  business_name: z.string().trim().min(2, 'Enter the business name'),
  business_type: z.string(),
  country: z.string().regex(/^[A-Za-z]{2}$/, 'Use a two-letter country code'),
  display_currency: z.string().regex(/^[A-Za-z]{3}$/, 'Use a three-letter currency code'),
  timezone: z.string().min(1),
})

export function SettingsPage() {
  const { me, refresh, config } = useSession()
  const { notify } = useToast()
  const [profileError, setProfileError] = useState<string | null>(null)
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const merchant = me?.merchant

  const profile = useForm<z.infer<typeof profileSchema>>({
    resolver: zodResolver(profileSchema),
    values: {
      business_name: merchant?.business_name ?? '',
      business_type: merchant?.business_type ?? 'sole_trader',
      country: merchant?.country ?? '',
      display_currency: merchant?.display_currency ?? 'USD',
      timezone: merchant?.timezone ?? 'UTC',
    },
  })
  const nameForm = useForm({ defaultValues: { full_name: me?.user.full_name ?? '' }, values: { full_name: me?.user.full_name ?? '' } })
  const passwordForm = useForm({ defaultValues: { current_password: '', new_password: '', confirm: '' } })

  const saveProfile = profile.handleSubmit(async (values) => {
    setProfileError(null)
    try {
      await updateMerchant({
        ...values,
        country: values.country.toUpperCase(),
        display_currency: values.display_currency.toUpperCase(),
      })
      await refresh()
      notify({ tone: 'success', title: 'Business profile saved' })
    } catch (err) {
      setProfileError(err instanceof ApiError ? err.message : 'Could not save the profile.')
    }
  })

  const saveName = nameForm.handleSubmit(async (values) => {
    try {
      await updateMe({ full_name: values.full_name })
      await refresh()
      notify({ tone: 'success', title: 'Name updated' })
    } catch (err) {
      notify({ tone: 'danger', title: err instanceof ApiError ? err.message : 'Could not update your name.' })
    }
  })

  const savePassword = passwordForm.handleSubmit(async (values) => {
    setPasswordError(null)
    if (values.new_password.length < 10) {
      setPasswordError('Use at least 10 characters.')
      return
    }
    if (values.new_password !== values.confirm) {
      setPasswordError('Passwords do not match.')
      return
    }
    try {
      await changePassword({ current_password: values.current_password, new_password: values.new_password })
      passwordForm.reset()
      notify({ tone: 'success', title: 'Password updated' })
    } catch (err) {
      setPasswordError(err instanceof ApiError ? err.message : 'Could not update the password.')
    }
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="type-page-title">Settings</h1>
        <p className="type-body mt-1 text-muted">Your profile and sign-in options. Display currency never overrides a record’s source currency.</p>
      </div>

      <Card>
        <CardHeader title="Account" description={me?.user.email} />
        <CardBody className="space-y-4">
          {!me?.user.email_verified && (
            <Alert
              tone="warning"
              title="Email not confirmed"
              action={
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() =>
                    void requestEmailVerification().then((r) =>
                      notify({ tone: 'info', title: deliveryMessage(r.email?.delivery_mode, r.email?.delivered ?? false) }),
                    )
                  }
                >
                  Send confirmation
                </Button>
              }
            >
              This is email-ownership verification, not two-factor authentication.
            </Alert>
          )}
          <form onSubmit={saveName} className="grid gap-4 sm:grid-cols-[1fr_auto] sm:items-end">
            <Input label="Full name" {...nameForm.register('full_name')} />
            <Button type="submit" variant="secondary" loading={nameForm.formState.isSubmitting}>
              Save name
            </Button>
          </form>
        </CardBody>
      </Card>

      {merchant && (
        <Card>
          <CardHeader title="Business profile" />
          <CardBody>
            {profileError && <Alert tone="danger" title={profileError} className="mb-4" />}
            <form onSubmit={saveProfile} className="grid gap-4 sm:grid-cols-2">
              <Input label="Business name" className="sm:col-span-2" error={profile.formState.errors.business_name?.message} {...profile.register('business_name')} />
              <Select label="Business type" {...profile.register('business_type')}>
                {(merchant.business_type_options ?? []).map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </Select>
              <Input label="Country" hint="ISO 3166-1 alpha-2, e.g. US" error={profile.formState.errors.country?.message} {...profile.register('country')} />
              <Input
                label="Display currency"
                hint="Used for formatting only. Source currencies are never converted."
                error={profile.formState.errors.display_currency?.message}
                {...profile.register('display_currency')}
              />
              <Input label="Time zone" hint="IANA name, e.g. America/New_York" error={profile.formState.errors.timezone?.message} {...profile.register('timezone')} />
              <div className="sm:col-span-2">
                <Button type="submit" loading={profile.formState.isSubmitting}>
                  Save business profile
                </Button>
              </div>
            </form>
          </CardBody>
        </Card>
      )}

      <Card>
        <CardHeader title="Password" description={me?.user.has_password ? 'Change the password for this account.' : 'This account was created with Google and has no password yet.'} />
        <CardBody>
          {passwordError && <Alert tone="danger" title={passwordError} className="mb-4" />}
          {config?.email_delivery_mode !== 'smtp' && (
            <Alert tone="info" title="Password recovery emails follow the same delivery mode as the rest of the app." className="mb-4" />
          )}
          <form onSubmit={savePassword} className="grid max-w-md gap-4">
            {me?.user.has_password && (
              <Input label="Current password" type="password" autoComplete="current-password" {...passwordForm.register('current_password')} />
            )}
            <Input label="New password" type="password" autoComplete="new-password" {...passwordForm.register('new_password')} />
            <Input label="Confirm new password" type="password" autoComplete="new-password" {...passwordForm.register('confirm')} />
            <Button type="submit" loading={passwordForm.formState.isSubmitting}>
              Update password
            </Button>
          </form>
        </CardBody>
      </Card>
    </div>
  )
}
