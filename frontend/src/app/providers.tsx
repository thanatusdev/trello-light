import { type QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { type ReactNode, useEffect } from 'react'

import { Toaster } from '@/components/ui/sonner'
import { TooltipProvider } from '@/components/ui/tooltip'
import { tokenSubject } from '@/lib/jwt'
import { AUTH_STORAGE_KEY, useAuthStore } from '@/stores/auth-store'

interface AppProvidersProps {
  queryClient: QueryClient
  children: ReactNode
}

export function AppProviders({ queryClient, children }: AppProvidersProps) {
  // Whenever the session ends (sign-out or failed refresh) or switches to another user
  // (signed in again in another tab), drop every cached response so the next user never
  // sees the previous user's data.
  useEffect(
    () =>
      useAuthStore.subscribe((state, previous) => {
        if (previous.refreshToken === null || state.refreshToken === previous.refreshToken) return
        if (state.refreshToken === null) {
          queryClient.clear()
        } else if (tokenSubject(state.refreshToken) !== tokenSubject(previous.refreshToken)) {
          // The in-memory access token is the previous user's: drop it so the next
          // request refreshes with the new refresh token.
          useAuthStore.setState({ accessToken: null })
          queryClient.clear()
        }
      }),
    [queryClient],
  )

  // Another tab signed in, out, or rotated the shared refresh token: reload it here, so
  // the subscription above sees the change.
  useEffect(() => {
    const onStorage = (event: StorageEvent) => {
      if (event.key === AUTH_STORAGE_KEY) void useAuthStore.persist.rehydrate()
    }
    window.addEventListener('storage', onStorage)
    return () => {
      window.removeEventListener('storage', onStorage)
    }
  }, [])

  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>{children}</TooltipProvider>
      <Toaster richColors position="top-center" />
    </QueryClientProvider>
  )
}
