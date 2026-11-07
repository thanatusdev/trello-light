import { render } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, type InitialEntry, RouterProvider } from 'react-router'

import { AppProviders } from '@/app/providers'
import { createQueryClient } from '@/app/query-client'
import { routes } from '@/app/routes'

/** Render the real route tree at `entry`, with fresh providers. */
export function renderApp(entry: InitialEntry = '/') {
  const queryClient = createQueryClient({ retry: false })
  const router = createMemoryRouter(routes, { initialEntries: [entry] })
  const user = userEvent.setup()
  render(
    <AppProviders queryClient={queryClient}>
      <RouterProvider router={router} />
    </AppProviders>,
  )
  return { router, queryClient, user }
}
