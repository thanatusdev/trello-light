import { useEffect, useState } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router'

import { refreshSession } from '@/api/client'
import { FullScreenLoader } from '@/components/FullScreenLoader'
import { Button } from '@/components/ui/button'
import { useAuthStore } from '@/stores/auth-store'

import { useMe, useSignOut } from './use-session'

export function ProtectedRoute() {
  const location = useLocation()
  const refreshToken = useAuthStore((state) => state.refreshToken)
  const accessToken = useAuthStore((state) => state.accessToken)
  const me = useMe()
  const signOut = useSignOut()

  // After a reload only the refresh token survives: exchange it for an access token.
  // A refused token clears the session, which re-renders this route as a redirect; a
  // transient failure (offline, 5xx, 429) keeps it and offers a retry.
  const needsRestore = refreshToken !== null && accessToken === null
  const [restoreAttempt, setRestoreAttempt] = useState(0)
  const [restoreFailed, setRestoreFailed] = useState(false)
  useEffect(() => {
    if (!needsRestore) return
    let active = true
    refreshSession().catch(() => {
      if (active) setRestoreFailed(true)
    })
    return () => {
      active = false
    }
  }, [needsRestore, restoreAttempt])

  if (refreshToken === null) {
    const from = location.pathname + location.search + location.hash
    return <Navigate to="/login" replace state={{ from }} />
  }

  if (me.isError || (needsRestore && restoreFailed)) {
    const retry = () => {
      if (needsRestore) {
        setRestoreFailed(false)
        setRestoreAttempt((n) => n + 1)
      } else {
        void me.refetch()
      }
    }
    return (
      <main className="flex min-h-svh flex-col items-center justify-center gap-4 p-4 text-center">
        <p className="text-muted-foreground">We couldn&apos;t load your account.</p>
        <div className="flex gap-2">
          <Button onClick={retry}>Try again</Button>
          <Button variant="outline" onClick={signOut}>
            Sign out
          </Button>
        </div>
      </main>
    )
  }

  if (!me.isSuccess) return <FullScreenLoader />

  return <Outlet />
}
