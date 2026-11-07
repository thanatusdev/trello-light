import createClient, { type Middleware } from 'openapi-fetch'
import { toast } from 'sonner'
import { z } from 'zod'

import { useAuthStore } from '@/stores/auth-store'

import { toApiError } from './errors'
import type { paths } from './schema'

/** Endpoints that must never carry a bearer token or trigger a refresh. */
const UNAUTHENTICATED_PATHS = new Set([
  '/api/v1/auth/login',
  '/api/v1/auth/logout',
  '/api/v1/auth/refresh',
  '/api/v1/auth/register',
])

/** Refresh responses that mean the refresh token itself is no good. */
const REFRESH_REJECTED = new Set([400, 401])

/** The refresh token is missing or was refused; the session has been cleared. */
export class SessionExpiredError extends Error {
  constructor(message = 'Your session has expired.') {
    super(message)
    this.name = 'SessionExpiredError'
  }
}

export const tokenResponseSchema = z.object({
  access_token: z.string().min(1),
  refresh_token: z.string().min(1),
  token_type: z.literal('bearer'),
})

interface Replay {
  /** Untouched copy of the request, so its body can be sent again. */
  request: Request
  /** Access token the original request went out with. */
  sentWith: string | null
}

const replays = new Map<string, Replay>()

const authMiddleware: Middleware = {
  onRequest({ request, schemaPath, id }) {
    if (UNAUTHENTICATED_PATHS.has(schemaPath)) return
    const token = useAuthStore.getState().accessToken
    if (token) request.headers.set('Authorization', `Bearer ${token}`)
    replays.set(id, { request: request.clone(), sentWith: token })
    return request
  },

  async onResponse({ response, id }) {
    const replay = replays.get(id)
    replays.delete(id)
    if (response.status !== 401 || !replay) return response

    // Another request may already have refreshed while this one was in flight.
    let token = useAuthStore.getState().accessToken
    if (!token || token === replay.sentWith) {
      try {
        token = await refreshSession()
      } catch (error) {
        // Signed out: answer with the original 401 (protected routes redirect to login).
        if (error instanceof SessionExpiredError) return response
        // Transient (network, 5xx, 429): fail this request with that error, still signed in.
        throw error
      }
    }

    // Retry exactly once, outside the middleware chain, so a second 401 can't loop.
    replay.request.headers.set('Authorization', `Bearer ${token}`)
    return globalThis.fetch(replay.request)
  },

  onError({ id }) {
    replays.delete(id)
  },
}

export const apiClient = createClient<paths>({
  baseUrl: window.location.origin,
  // Resolve fetch lazily so test interceptors patched after import still apply.
  fetch: (request) => globalThis.fetch(request),
})
apiClient.use(authMiddleware)

let inflightRefresh: Promise<string> | null = null

/**
 * Exchange the stored refresh token for a new token pair. Concurrent callers share a
 * single request.
 *
 * - The token is refused (400/401) or missing: the session is cleared (which sends
 *   protected routes to the login page), the user is told, and this rejects with
 *   `SessionExpiredError`.
 * - Anything else (network error, 5xx, 429, malformed body) is treated as transient:
 *   the session is kept and the error (`TypeError`, `ApiError`, ...) is rethrown.
 */
export function refreshSession(): Promise<string> {
  inflightRefresh ??= doRefresh().finally(() => {
    inflightRefresh = null
  })
  return inflightRefresh
}

/** Held while refreshing, so tabs sharing one refresh token take turns spending it. */
const REFRESH_LOCK = 'trello-light-auth-refresh'

async function withCrossTabLock<T>(callback: () => Promise<T>): Promise<T> {
  // Web Locks are missing in old browsers and jsdom; one tab on its own needs no lock.
  const locks = (navigator as Partial<Navigator>).locks
  if (!locks) return callback()
  return await locks.request(REFRESH_LOCK, callback)
}

/**
 * Refresh tokens are single-use and every tab shares the persisted one. Inside the lock,
 * reload it first: another tab may have rotated it, which would make ours a replay.
 */
function doRefresh(): Promise<string> {
  return withCrossTabLock(async () => {
    await useAuthStore.persist.rehydrate()
    return refreshWith(useAuthStore.getState().refreshToken)
  })
}

async function refreshWith(refreshToken: string | null): Promise<string> {
  const { setTokens, clear } = useAuthStore.getState()
  if (!refreshToken) throw new SessionExpiredError('No refresh token')

  const { data, error, response } = await apiClient.POST('/api/v1/auth/refresh', {
    body: { refresh_token: refreshToken },
  })
  if (REFRESH_REJECTED.has(response.status)) {
    clear()
    toast.error('Your session has expired. Please sign in again.')
    throw new SessionExpiredError()
  }
  if (!response.ok) throw toApiError(response, error)
  const tokens = tokenResponseSchema.parse(data)
  setTokens(tokens)
  return tokens.access_token
}
