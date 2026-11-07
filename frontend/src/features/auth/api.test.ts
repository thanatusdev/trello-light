import { http, HttpResponse } from 'msw'

import { ApiError } from '@/api/errors'
import { useAuthStore } from '@/stores/auth-store'
import { API, demoUser, tokens } from '@/test/handlers'
import { server } from '@/test/server'

import { fetchMe, login, logout } from './api'

describe('login', () => {
  it('posts the credentials form-encoded, with the email as username', async () => {
    const seen: { contentType?: string | null; form?: URLSearchParams } = {}
    server.use(
      http.post(`${API}/auth/login`, async ({ request }) => {
        seen.contentType = request.headers.get('Content-Type')
        seen.form = new URLSearchParams(await request.text())
        return HttpResponse.json(tokens.initial)
      }),
    )

    const result = await login({ email: 'alice@example.com', password: 'Demo1234!' })

    expect(result).toEqual(tokens.initial)
    expect(seen.contentType).toContain('application/x-www-form-urlencoded')
    expect(Object.fromEntries(seen.form ?? [])).toEqual({
      username: 'alice@example.com',
      password: 'Demo1234!',
    })
  })

  it('throws an ApiError with the status on bad credentials', async () => {
    await expect(login({ email: 'alice@example.com', password: 'nope' })).rejects.toMatchObject({
      status: 401,
    })
  })

  it('exposes Retry-After when rate limited', async () => {
    server.use(
      http.post(`${API}/auth/login`, () =>
        HttpResponse.json(
          { detail: 'Rate limit exceeded, try again later' },
          { status: 429, headers: { 'Retry-After': '30' } },
        ),
      ),
    )

    const error = await login({ email: 'a@b.co', password: 'x' }).catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 429, retryAfter: 30 })
  })

  it('rejects a response that does not match the token schema', async () => {
    server.use(http.post(`${API}/auth/login`, () => HttpResponse.json({ access_token: 1 })))

    await expect(login({ email: 'alice@example.com', password: 'Demo1234!' })).rejects.toThrow()
  })
})

describe('fetchMe', () => {
  it('returns the parsed current user', async () => {
    useAuthStore.getState().setTokens(tokens.initial)

    await expect(fetchMe()).resolves.toEqual(demoUser)
  })

  it('rejects a malformed user payload', async () => {
    server.use(http.get(`${API}/auth/me`, () => HttpResponse.json({ id: 'not-a-uuid' })))
    useAuthStore.getState().setTokens(tokens.initial)

    await expect(fetchMe()).rejects.toThrow()
  })

  it('throws an ApiError when not authenticated', async () => {
    await expect(fetchMe()).rejects.toBeInstanceOf(ApiError)
  })
})

describe('logout', () => {
  it('posts the refresh token without a bearer token', async () => {
    useAuthStore.getState().setTokens(tokens.initial)
    const seen: { body?: unknown; authorization?: string | null } = {}
    server.use(
      http.post(`${API}/auth/logout`, async ({ request }) => {
        seen.body = await request.json()
        seen.authorization = request.headers.get('Authorization')
        return new HttpResponse(null, { status: 204 })
      }),
    )

    await logout('refresh-1')

    expect(seen).toEqual({ body: { refresh_token: 'refresh-1' }, authorization: null })
  })

  it('ignores server and network failures', async () => {
    server.use(http.post(`${API}/auth/logout`, () => HttpResponse.json({}, { status: 503 })))
    await expect(logout('refresh-1')).resolves.toBeUndefined()

    server.use(http.post(`${API}/auth/logout`, () => HttpResponse.error()))
    await expect(logout('refresh-1')).resolves.toBeUndefined()
  })
})
