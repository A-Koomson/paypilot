/**
 * Central API client. All backend traffic goes through here so that CSRF handling,
 * credentials, error normalisation and session-expiry handling live in one place.
 * No secrets or tokens are ever stored in the browser; authentication is an HTTP-only cookie.
 */

const BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details?: unknown
  readonly requestId?: string

  constructor(init: { status: number; code: string; message: string; details?: unknown; requestId?: string }) {
    super(init.message)
    this.name = 'ApiError'
    this.status = init.status
    this.code = init.code
    this.details = init.details
    this.requestId = init.requestId
  }

  /** Field-level validation messages, keyed by field name. */
  get fieldErrors(): Record<string, string> {
    if (this.code !== 'validation_error' || typeof this.details !== 'object' || this.details === null) return {}
    const out: Record<string, string> = {}
    for (const [key, value] of Object.entries(this.details as Record<string, unknown>)) {
      out[key] = Array.isArray(value) ? String(value[0]) : String(value)
    }
    return out
  }
}

type Listener = () => void
const unauthenticatedListeners = new Set<Listener>()
export function onUnauthenticated(listener: Listener): () => void {
  unauthenticatedListeners.add(listener)
  return () => unauthenticatedListeners.delete(listener)
}

let csrfToken: string | null = null
let csrfInflight: Promise<string> | null = null

async function fetchCsrf(): Promise<string> {
  if (csrfToken) return csrfToken
  csrfInflight ??= fetch(`${BASE}/api/auth/csrf/`, { credentials: 'include' })
    .then(async (res) => {
      if (!res.ok) throw new Error('csrf')
      const data = (await res.json()) as { csrfToken: string }
      csrfToken = data.csrfToken
      return csrfToken
    })
    .finally(() => {
      csrfInflight = null
    })
  return csrfInflight
}

export function resetCsrfToken(): void {
  csrfToken = null
}

const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  query?: Record<string, string | number | boolean | undefined | null>
  signal?: AbortSignal
  /** Do not treat a 401 as a session expiry (used by login/me probes). */
  quiet401?: boolean
}

function buildUrl(path: string, query?: RequestOptions['query']): string {
  const url = `${BASE}${path}`
  if (!query) return url
  const params = new URLSearchParams()
  for (const [k, v] of Object.entries(query)) {
    if (v !== undefined && v !== null && v !== '') params.set(k, String(v))
  }
  const qs = params.toString()
  return qs ? `${url}?${qs}` : url
}

async function toApiError(res: Response): Promise<ApiError> {
  let payload: unknown
  try {
    payload = await res.json()
  } catch {
    payload = undefined
  }
  const err = (payload as { error?: { code?: string; message?: string; details?: unknown; request_id?: string } })?.error
  return new ApiError({
    status: res.status,
    code: err?.code ?? (res.status >= 500 ? 'server_error' : 'error'),
    message: err?.message ?? (res.status >= 500 ? 'The server had a problem. Please try again.' : 'Request failed.'),
    details: err?.details,
    requestId: err?.request_id,
  })
}

export async function api<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? 'GET'
  const unsafe = !SAFE_METHODS.has(method)

  const attempt = async (): Promise<Response> => {
    const headers: Record<string, string> = { Accept: 'application/json' }
    if (options.body !== undefined) headers['Content-Type'] = 'application/json'
    if (unsafe) headers['X-CSRFToken'] = await fetchCsrf()
    return fetch(buildUrl(path, options.query), {
      method,
      headers,
      credentials: 'include',
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      signal: options.signal,
    })
  }

  let res: Response
  try {
    res = await attempt()
    if (res.status === 403 && unsafe) {
      const probe = await res.clone().json().catch(() => undefined)
      if (String((probe as { error?: { message?: string } })?.error?.message ?? '').includes('CSRF')) {
        resetCsrfToken()
        res = await attempt()
      }
    }
  } catch (cause) {
    if ((cause as Error)?.name === 'AbortError') throw cause
    throw new ApiError({
      status: 0,
      code: 'network_error',
      message: 'Could not reach the server. Check your connection and try again.',
    })
  }

  if (!res.ok) {
    const error = await toApiError(res)
    if (error.status === 401 && !options.quiet401) unauthenticatedListeners.forEach((l) => l())
    throw error
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const apiGet = <T>(path: string, query?: RequestOptions['query'], signal?: AbortSignal) =>
  api<T>(path, { query, signal })
export const apiPost = <T>(path: string, body?: unknown, opts?: Pick<RequestOptions, 'quiet401'>) =>
  api<T>(path, { method: 'POST', body: body ?? {}, ...opts })
export const apiPatch = <T>(path: string, body: unknown) => api<T>(path, { method: 'PATCH', body })
export const apiDelete = <T>(path: string) => api<T>(path, { method: 'DELETE' })
