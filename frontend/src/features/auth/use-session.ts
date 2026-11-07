import { useMutation, useQuery } from '@tanstack/react-query'
import { useCallback } from 'react'

import { useAuthStore } from '@/stores/auth-store'

import { fetchMe, login, logout, type Registration, registerAccount } from './api'
import { SignInAfterRegisterError } from './auth-errors'

export const meQueryKey = ['auth', 'me'] as const

/** The signed-in user. Only runs once an access token is available. */
export function useMe() {
  const hasAccessToken = useAuthStore((state) => state.accessToken !== null)
  return useQuery({ queryKey: meQueryKey, queryFn: fetchMe, enabled: hasAccessToken })
}

export function useLogin() {
  const setTokens = useAuthStore((state) => state.setTokens)
  return useMutation({ mutationFn: login, onSuccess: setTokens })
}

/** Create an account, then sign in with it (PublicOnlyRoute then leaves the page). */
export function useRegister() {
  const setTokens = useAuthStore((state) => state.setTokens)
  return useMutation({
    mutationFn: async (registration: Registration) => {
      await registerAccount(registration)
      try {
        return await login({ email: registration.email, password: registration.password })
      } catch (error) {
        throw new SignInAfterRegisterError(error)
      }
    },
    onSuccess: setTokens,
  })
}

/** Sign out at once, then revoke the session on the server in the background. */
export function useSignOut() {
  return useCallback(() => {
    const { refreshToken, clear } = useAuthStore.getState()
    clear()
    if (refreshToken) void logout(refreshToken)
  }, [])
}
