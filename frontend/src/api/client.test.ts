import { http, HttpResponse } from 'msw'
import { toast } from 'sonner'

import { AUTH_STORAGE_KEY, useAuthStore } from '@/stores/auth-store'
import { API, demoUser, tokens, unauthorized } from '@/test/handlers'
import { server } from '@/test/server'

import { apiClient, refreshSession, SessionExpiredError } from './client'
import { ApiError } from './errors'

vi.mock('sonner', () => ({ toast: { error: vi.fn() } }))

function signIn(accessToken: string, refreshToken = 'refresh-1') {
  useAuthStore.getState().setTokens({ access_token: accessToken, refresh_token: refreshToken })
}

/** Counts refresh calls while delegating to the default handler. */
function countRefreshes() {
  const calls: string[] = []
  server.events.on('request:start', ({ request }) => {
    if (request.url.endsWith('/auth/refresh')) calls.push(request.url)
  })
  return calls
}

describe('apiClient auth handling', () => {
  afterEach(() => {
    server.events.removeAllListeners()
  })

  it('injects the bearer token', async () => {
    let seen: string | null = null
    server.use(
      http.get(`${API}/auth/me`, ({ request }) => {
        seen = request.headers.get('Authorization')
        return HttpResponse.json(demoUser)
      }),
    )
    signIn('access-1')

    const { data } = await apiClient.GET('/api/v1/auth/me')

    expect(seen).toBe('Bearer access-1')
    expect(data).toEqual(demoUser)
  })

  it('sends no Authorization header when signed out', async () => {
    let seen: string | null = 'unset'
    server.use(
      http.get(`${API}/auth/me`, ({ request }) => {
        seen = request.headers.get('Authorization')
        return unauthorized()
      }),
    )

    const { response } = await apiClient.GET('/api/v1/auth/me')

    expect(seen).toBeNull()
    expect(response.status).toBe(401)
  })

  it('refreshes once for concurrent 401s and retries every request with the new token', async () => {
    const refreshes = countRefreshes()
    const authHeaders: (string | null)[] = []
    server.use(
      http.get(`${API}/auth/me`, ({ request }) => {
        const auth = request.headers.get('Authorization')
        authHeaders.push(auth)
        return auth === 'Bearer access-2' ? HttpResponse.json(demoUser) : unauthorized()
      }),
    )
    signIn('expired')

    const results = await Promise.all([
      apiClient.GET('/api/v1/auth/me'),
      apiClient.GET('/api/v1/auth/me'),
      apiClient.GET('/api/v1/auth/me'),
    ])

    expect(refreshes).toHaveLength(1)
    expect(results.map((r) => r.data)).toEqual([demoUser, demoUser, demoUser])
    expect(authHeaders.filter((h) => h === 'Bearer access-2')).toHaveLength(3)
    expect(useAuthStore.getState()).toMatchObject({
      accessToken: tokens.refreshed.access_token,
      refreshToken: tokens.refreshed.refresh_token,
    })
  })

  it('replays the request body on retry', async () => {
    const bodies: unknown[] = []
    server.use(
      http.post(`${API}/statuses`, async ({ request }) => {
        bodies.push(await request.json())
        return request.headers.get('Authorization') === 'Bearer access-2'
          ? HttpResponse.json({ id: 'new' }, { status: 201 })
          : unauthorized()
      }),
    )
    signIn('expired')

    const { response } = await apiClient.POST('/api/v1/statuses', {
      body: { name: 'Review', is_done: false },
    })

    expect(response.status).toBe(201)
    expect(bodies).toEqual([
      { name: 'Review', is_done: false },
      { name: 'Review', is_done: false },
    ])
  })

  it('does not refresh again when the token was already refreshed by another request', async () => {
    const refreshes = countRefreshes()
    // The request goes out with the old token, but by the time its 401 arrives
    // the store already holds a newer one.
    server.use(
      http.get(`${API}/auth/me`, ({ request }) => {
        if (request.headers.get('Authorization') === 'Bearer old') {
          signIn('access-9', 'refresh-9')
          return unauthorized()
        }
        return HttpResponse.json(demoUser)
      }),
    )
    signIn('old')

    const { data } = await apiClient.GET('/api/v1/auth/me')

    expect(data).toEqual(demoUser)
    expect(refreshes).toHaveLength(0)
  })

  it('retries only once when the retried request is also rejected', async () => {
    let meCalls = 0
    server.use(
      http.get(`${API}/auth/me`, () => {
        meCalls += 1
        return unauthorized()
      }),
    )
    signIn('expired')

    const { response } = await apiClient.GET('/api/v1/auth/me')

    expect(response.status).toBe(401)
    expect(meCalls).toBe(2)
  })

  it('signs out and notifies once when the refresh fails', async () => {
    server.use(
      http.post(`${API}/auth/refresh`, () => unauthorized()),
      http.get(`${API}/auth/me`, () => unauthorized()),
    )
    signIn('expired')

    const results = await Promise.all([
      apiClient.GET('/api/v1/auth/me'),
      apiClient.GET('/api/v1/auth/me'),
    ])

    expect(results.map((r) => r.response.status)).toEqual([401, 401])
    expect(useAuthStore.getState()).toMatchObject({ accessToken: null, refreshToken: null })
    expect(toast.error).toHaveBeenCalledTimes(1)
  })

  it('signs out when the refresh token is rejected as malformed (400)', async () => {
    server.use(
      http.post(`${API}/auth/refresh`, () =>
        HttpResponse.json({ detail: 'Invalid token' }, { status: 400 }),
      ),
      http.get(`${API}/auth/me`, () => unauthorized()),
    )
    signIn('expired')

    const { response } = await apiClient.GET('/api/v1/auth/me')

    expect(response.status).toBe(401)
    expect(useAuthStore.getState().refreshToken).toBeNull()
    expect(toast.error).toHaveBeenCalledTimes(1)
  })

  it.each([
    ['a server error', 503, {}],
    ['rate limiting', 429, { 'Retry-After': '12' }],
  ])(
    'keeps the session and fails the request normally when the refresh hits %s',
    async (_case, status, headers) => {
      server.use(
        http.post(`${API}/auth/refresh`, () =>
          HttpResponse.json({ detail: 'Try later' }, { status, headers }),
        ),
        http.get(`${API}/auth/me`, () => unauthorized()),
      )
      signIn('expired')

      const failure = await apiClient.GET('/api/v1/auth/me').catch((error: unknown) => error)

      expect(failure).toBeInstanceOf(ApiError)
      expect(failure).toMatchObject({ status })
      expect(useAuthStore.getState()).toMatchObject({
        accessToken: 'expired',
        refreshToken: 'refresh-1',
      })
      expect(toast.error).not.toHaveBeenCalled()
    },
  )

  it('passes the retry delay of a rate-limited refresh on to the caller', async () => {
    server.use(
      http.post(`${API}/auth/refresh`, () =>
        HttpResponse.json(
          { detail: 'Slow down' },
          { status: 429, headers: { 'Retry-After': '12' } },
        ),
      ),
      http.get(`${API}/auth/me`, () => unauthorized()),
    )
    signIn('expired')

    await expect(apiClient.GET('/api/v1/auth/me')).rejects.toMatchObject({ retryAfter: 12 })
  })

  it('keeps the session when the refresh cannot reach the server', async () => {
    server.use(
      http.post(`${API}/auth/refresh`, () => HttpResponse.error()),
      http.get(`${API}/auth/me`, () => unauthorized()),
    )
    signIn('expired')

    await expect(apiClient.GET('/api/v1/auth/me')).rejects.toThrow(TypeError)
    expect(useAuthStore.getState().refreshToken).toBe('refresh-1')
    expect(toast.error).not.toHaveBeenCalled()
  })

  it('never tries to refresh on a failed login', async () => {
    const refreshes = countRefreshes()
    signIn('expired')

    const { response } = await apiClient.POST('/api/v1/auth/login', {
      body: { username: 'x@example.com', password: 'wrong', scope: '' },
      bodySerializer: (body) => new URLSearchParams(body as Record<string, string>),
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })

    expect(response.status).toBe(401)
    expect(refreshes).toHaveLength(0)
  })
})

describe('refreshSession', () => {
  it('fails fast without a refresh token', async () => {
    await expect(refreshSession()).rejects.toThrow(SessionExpiredError)
    expect(toast.error).not.toHaveBeenCalled()
  })

  it('shares one in-flight refresh between callers', async () => {
    const refreshes = countRefreshes()
    useAuthStore.setState({ refreshToken: 'refresh-1', accessToken: null })

    const [a, b] = await Promise.all([refreshSession(), refreshSession()])

    expect(a).toBe('access-2')
    expect(b).toBe('access-2')
    expect(refreshes).toHaveLength(1)
    server.events.removeAllListeners()
  })

  it('treats a malformed refresh response as a failure without signing out', async () => {
    server.use(http.post(`${API}/auth/refresh`, () => HttpResponse.json({ nope: true })))
    useAuthStore.setState({ refreshToken: 'refresh-1', accessToken: null })

    await expect(refreshSession()).rejects.toThrow()
    expect(useAuthStore.getState().refreshToken).toBe('refresh-1')
  })

  it('uses the newest refresh token another tab has stored', async () => {
    const sent: unknown[] = []
    server.use(
      http.post(`${API}/auth/refresh`, async ({ request }) => {
        sent.push(await request.json())
        return HttpResponse.json(tokens.refreshed)
      }),
    )
    signIn('access-1', 'refresh-1')
    // Another tab rotated the shared token; this tab still holds the spent one in memory.
    localStorage.setItem(
      AUTH_STORAGE_KEY,
      JSON.stringify({ state: { refreshToken: 'refresh-from-other-tab' }, version: 0 }),
    )

    await refreshSession()

    expect(sent).toEqual([{ refresh_token: 'refresh-from-other-tab' }])
  })

  it('holds a cross-tab lock while refreshing', async () => {
    const request = vi.fn((_name: string, callback: () => Promise<unknown>) => callback())
    Object.defineProperty(navigator, 'locks', { value: { request }, configurable: true })
    try {
      signIn('access-1')

      await expect(refreshSession()).resolves.toBe('access-2')

      expect(request).toHaveBeenCalledWith('trello-light-auth-refresh', expect.any(Function))
    } finally {
      Reflect.deleteProperty(navigator, 'locks')
    }
  })

  it('rejects with SessionExpiredError and signs out when the token is refused', async () => {
    server.use(http.post(`${API}/auth/refresh`, () => unauthorized()))
    useAuthStore.setState({ refreshToken: 'refresh-1', accessToken: null })

    await expect(refreshSession()).rejects.toThrow(SessionExpiredError)
    expect(useAuthStore.getState().refreshToken).toBeNull()
  })
})
