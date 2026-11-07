import { AUTH_STORAGE_KEY, useAuthStore } from './auth-store'

const pair = { access_token: 'a', refresh_token: 'r', token_type: 'bearer' as const }

describe('auth store', () => {
  it('starts signed out', () => {
    const { accessToken, refreshToken } = useAuthStore.getState()
    expect(accessToken).toBeNull()
    expect(refreshToken).toBeNull()
  })

  it('stores both tokens in memory but persists only the refresh token', () => {
    useAuthStore.getState().setTokens(pair)

    expect(useAuthStore.getState()).toMatchObject({ accessToken: 'a', refreshToken: 'r' })
    const persisted = JSON.parse(localStorage.getItem(AUTH_STORAGE_KEY) ?? '{}') as {
      state: Record<string, unknown>
    }
    expect(persisted.state).toEqual({ refreshToken: 'r' })
  })

  it('clear() forgets both tokens and the persisted refresh token', () => {
    useAuthStore.getState().setTokens(pair)
    useAuthStore.getState().clear()

    expect(useAuthStore.getState()).toMatchObject({ accessToken: null, refreshToken: null })
    const persisted = JSON.parse(localStorage.getItem(AUTH_STORAGE_KEY) ?? '{}') as {
      state?: Record<string, unknown>
    }
    expect(persisted.state?.refreshToken ?? null).toBeNull()
  })
})
