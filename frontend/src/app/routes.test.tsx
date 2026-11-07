import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { toast } from 'sonner'

import { meQueryKey } from '@/features/auth/use-session'
import { useAuthStore } from '@/stores/auth-store'
import { API, demoUser, tokens, unauthorized } from '@/test/handlers'
import { renderApp } from '@/test/render'
import { server } from '@/test/server'

vi.mock('sonner', async (importOriginal) => {
  const actual = await importOriginal<typeof import('sonner')>()
  return { ...actual, toast: { error: vi.fn() } }
})

describe('routing and session', () => {
  it('sends anonymous visitors to the login page', async () => {
    const { router } = renderApp('/')

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
  })

  it('sends signed-in users away from the login page', async () => {
    useAuthStore.getState().setTokens(tokens.initial)
    const { router } = renderApp('/login')

    expect(await screen.findByText(demoUser.full_name)).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/board')
  })

  it('ignores redirect targets that leave the app', async () => {
    useAuthStore.getState().setTokens(tokens.initial)
    const { router } = renderApp({ pathname: '/login', state: { from: '//evil.example' } })

    await screen.findByText(demoUser.full_name)
    expect(router.state.location.pathname).toBe('/board')
  })

  it('restores the session from the refresh token after a reload', async () => {
    useAuthStore.setState({ accessToken: null, refreshToken: 'refresh-1' })
    renderApp('/')

    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
    expect(await screen.findByText(demoUser.full_name)).toBeInTheDocument()
    expect(useAuthStore.getState().accessToken).toBe(tokens.refreshed.access_token)
  })

  it('returns to login with a notice when the stored session is no longer valid', async () => {
    server.use(http.post(`${API}/auth/refresh`, () => unauthorized()))
    useAuthStore.setState({ accessToken: null, refreshToken: 'refresh-stale' })
    renderApp('/')

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(toast.error).toHaveBeenCalledWith('Your session has expired. Please sign in again.')
  })

  it('keeps the session and offers a retry when the server is unreachable after a reload', async () => {
    let down = true
    server.use(
      http.post(`${API}/auth/refresh`, () =>
        down ? HttpResponse.json({ detail: 'Unavailable' }, { status: 503 }) : undefined,
      ),
    )
    useAuthStore.setState({ accessToken: null, refreshToken: 'refresh-1' })
    const { user } = renderApp('/')

    expect(await screen.findByText("We couldn't load your account.")).toBeInTheDocument()
    expect(useAuthStore.getState().refreshToken).toBe('refresh-1')
    expect(toast.error).not.toHaveBeenCalled()

    down = false
    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByText(demoUser.full_name)).toBeInTheDocument()
  })

  it('offers a retry when the account cannot be loaded', async () => {
    let fail = true
    server.use(
      http.get(`${API}/auth/me`, () =>
        fail ? HttpResponse.json({ detail: 'boom' }, { status: 500 }) : HttpResponse.json(demoUser),
      ),
    )
    useAuthStore.getState().setTokens(tokens.initial)
    const { user } = renderApp('/')

    expect(await screen.findByText("We couldn't load your account.")).toBeInTheDocument()
    fail = false
    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByText(demoUser.full_name)).toBeInTheDocument()
  })

  it('signs out, clearing tokens and cached data and revoking the session', async () => {
    const revoked: unknown[] = []
    server.use(
      http.post(`${API}/auth/logout`, async ({ request }) => {
        revoked.push(await request.json())
        return new HttpResponse(null, { status: 204 })
      }),
    )
    useAuthStore.getState().setTokens(tokens.initial)
    const { user, queryClient, router } = renderApp('/')

    await user.click(await screen.findByRole('button', { name: 'Sign out' }))

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
    expect(useAuthStore.getState()).toMatchObject({ accessToken: null, refreshToken: null })
    expect(queryClient.getQueryData(meQueryKey)).toBeUndefined()
    await waitFor(() => {
      expect(revoked).toEqual([{ refresh_token: tokens.initial.refresh_token }])
    })
  })

  it('shows a not-found page for unknown routes', async () => {
    const { user, router } = renderApp('/nope')

    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument()
    await user.click(screen.getByRole('link', { name: 'Back to the board' }))

    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/login')
    })
  })
})
