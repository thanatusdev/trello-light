import { QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactElement } from 'react'

import { createQueryClient } from '@/app/query-client'
import { useAuthStore } from '@/stores/auth-store'

import { tokens } from './handlers'

/** Render a component on its own, signed in, with a fresh query client. */
export function renderWithQuery(ui: ReactElement) {
  useAuthStore.getState().setTokens(tokens.initial)
  const queryClient = createQueryClient({ retry: false })
  const user = userEvent.setup()
  const view = render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
  return { ...view, user, queryClient }
}
