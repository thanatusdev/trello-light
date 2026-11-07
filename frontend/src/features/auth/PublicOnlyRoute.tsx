import { Navigate, Outlet, useLocation } from 'react-router'

import { useAuthStore } from '@/stores/auth-store'

import { redirectTarget } from './redirect'

/** Pages for signed-out users only (e.g. login); signed-in users go back where they came from. */
export function PublicOnlyRoute() {
  const location = useLocation()
  const signedIn = useAuthStore((state) => state.refreshToken !== null)

  if (signedIn) return <Navigate to={redirectTarget(location.state)} replace />
  return <Outlet />
}
