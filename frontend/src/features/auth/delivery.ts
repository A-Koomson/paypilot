import type { DeliveryMode } from './types'

export function deliveryMessage(mode: DeliveryMode | string | undefined, sent?: boolean): string {
  if (mode === 'disabled' || sent === false && mode !== 'console') {
    return 'Email delivery is not configured. Nothing was sent.'
  }
  if (mode === 'console') {
    return 'No email provider is configured. The message was printed to the backend console instead of being delivered.'
  }
  return 'If an account exists for that address, a message is on its way. It can take a minute to arrive.'
}
