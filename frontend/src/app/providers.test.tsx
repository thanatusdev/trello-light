import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import { AUTH_STORAGE_KEY, useAuthStore } from '@/stores/auth-store'
import { API, demoUser, tokens } from '@/test/handlers'
import { fakeJwt } from '@/test/jwt'
import { renderApp } from '@/test/render'
import { server } from '@/test/server'

const probeKey = ['probe']

/** What another tab does: write the persisted session; the browser then fires `storage` here. */
function otherTabStores(refreshToken: string | null) {
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify({ state: { refreshToken }, version: 0 }))
  window.dispatchEvent(new StorageEvent('storage', { key: AUTH_STORAGE_KEY }))
}

async function signedIn(refreshToken: string) {
  useAuthStore.getState().setTokens({ access_token: 'access-1', refresh_token: refreshToken })
  const app = renderApp('/board')
  await screen.findByText(demoUser.full_name)
  app.queryClient.setQueryData(probeKey, 'cached')
  return app
}

describe('session shared across tabs', () => {
  it('signs this tab out when another tab signs out', async () => {
    const { router, queryClient } = await signedIn(tokens.initial.refresh_token)

    otherTabStores(null)

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
    expect(queryClient.getQueryData(probeKey)).toBeUndefined()
  })

  it("drops the previous user's data when another tab signs in as someone else", async () => {
    const { queryClient } = await signedIn(fakeJwt({ sub: 'alice', type: 'refresh' }))
    const bobs = fakeJwt({ sub: 'bob', type: 'refresh' })
    const refreshedWith: unknown[] = []
    server.use(
      http.post(`${API}/auth/refresh`, async ({ request }) => {
        refreshedWith.push(await request.json())
        return HttpResponse.json({ ...tokens.refreshed, refresh_token: bobs })
      }),
    )

    otherTabStores(bobs)

    await waitFor(() => {
      expect(queryClient.getQueryData(probeKey)).toBeUndefined()
    })
    // Alice's access token is dropped, so the next request refreshes as Bob.
    await waitFor(() => {
      expect(useAuthStore.getState().accessToken).toBe(tokens.refreshed.access_token)
    })
    expect(refreshedWith).toEqual([{ refresh_token: bobs }])
  })

  it("keeps the cache when another tab only rotates the same user's token", async () => {
    const { queryClient } = await signedIn(fakeJwt({ sub: 'alice', type: 'refresh', jti: '1' }))
    const rotated = fakeJwt({ sub: 'alice', type: 'refresh', jti: '2' })

    otherTabStores(rotated)

    await waitFor(() => {
      expect(useAuthStore.getState().refreshToken).toBe(rotated)
    })
    expect(queryClient.getQueryData(probeKey)).toBe('cached')
    expect(useAuthStore.getState().accessToken).toBe('access-1')
  })

  it('ignores storage changes to other keys', async () => {
    const { queryClient } = await signedIn(tokens.initial.refresh_token)
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify({ state: { refreshToken: null } }))

    window.dispatchEvent(new StorageEvent('storage', { key: 'something-else' }))

    expect(useAuthStore.getState().refreshToken).toBe(tokens.initial.refresh_token)
    expect(queryClient.getQueryData(probeKey)).toBe('cached')
  })
})
