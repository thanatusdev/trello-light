import { createBrowserRouter, RouterProvider } from 'react-router'

import { AppProviders } from './providers'
import { createQueryClient } from './query-client'
import { routes } from './routes'

const router = createBrowserRouter(routes)
const queryClient = createQueryClient()

export function App() {
  return (
    <AppProviders queryClient={queryClient}>
      <RouterProvider router={router} />
    </AppProviders>
  )
}
