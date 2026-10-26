import type { DeliveryMode } from './types'

export function deliveryMessage(mode: DeliveryMode | string | undefined, sent?: boolean): string {
  if (mode === 'console') {
    return 'No email provider is configured. The message was printed to the backend console instead of being delivered.'
  }
  if (mode === 'disabled') {
    return 'Email delivery is not configured. Nothing was sent.'
  }
  if (sent === false) {
    return 'The email provider did not accept the message. Nothing was delivered. Try again in a minute.'
  }
  return 'If an account exists for that address, a message is on its way. It can take a minute to arrive.'
}
