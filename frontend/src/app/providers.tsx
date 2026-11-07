import { type QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { type ReactNode, useEffect } from 'react'

import { Toaster } from '@/components/ui/sonner'
import { TooltipProvider } from '@/components/ui/tooltip'
import { useAuthStore } from '@/stores/auth-store'

interface AppProvidersProps {
  queryClient: QueryClient
  children: ReactNode
}

export function AppProviders({ queryClient, children }: AppProvidersProps) {
  // Whenever the session ends (sign-out or failed refresh), drop every cached
  // response so the next user never sees the previous user's data.
  useEffect(
    () =>
      useAuthStore.subscribe((state, previous) => {
        if (previous.refreshToken !== null && state.refreshToken === null) queryClient.clear()
      }),
    [queryClient],
  )

  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>{children}</TooltipProvider>
      <Toaster richColors position="top-center" />
    </QueryClientProvider>
  )
}
