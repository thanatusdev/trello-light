import { KanbanSquareIcon, ListIcon } from 'lucide-react'
import { NavLink, Outlet, useLocation } from 'react-router'

import { Button } from '@/components/ui/button'
import { useMe, useSignOut } from '@/features/auth/use-session'
import { cn } from '@/lib/utils'

/** Params that belong to one view only and shouldn't follow you to the other. */
const VIEW_ONLY_PARAMS = ['task', 'status', 'page']

function useSharedSearch() {
  const params = new URLSearchParams(useLocation().search)
  for (const key of VIEW_ONLY_PARAMS) params.delete(key)
  const search = params.toString()
  return search ? `?${search}` : ''
}

export function AppShell() {
  const { data: user } = useMe()
  const signOut = useSignOut()
  const search = useSharedSearch()

  const viewLink = ({ isActive }: { isActive: boolean }) =>
    cn(
      'flex items-center gap-1.5 rounded-md px-2.5 py-1 text-sm font-medium transition-colors',
      isActive
        ? 'bg-background text-foreground shadow-xs'
        : 'text-muted-foreground hover:text-foreground',
    )

  return (
    <div className="flex h-svh flex-col">
      <header className="flex items-center justify-between gap-3 border-b px-4 py-3">
        <div className="flex min-w-0 items-center gap-3">
          <span className="hidden font-semibold sm:inline">Trello Light</span>
          <nav aria-label="Views" className="flex rounded-lg bg-muted p-0.5">
            <NavLink to={`/board${search}`} className={viewLink}>
              <KanbanSquareIcon aria-hidden className="size-4" />
              Board
            </NavLink>
            <NavLink to={`/tasks${search}`} className={viewLink}>
              <ListIcon aria-hidden className="size-4" />
              List
            </NavLink>
          </nav>
        </div>
        <div className="flex min-w-0 items-center gap-3">
          <span className="truncate text-sm text-muted-foreground">{user?.full_name}</span>
          <Button variant="outline" size="sm" onClick={signOut}>
            Sign out
          </Button>
        </div>
      </header>
      <main className="min-h-0 flex-1 overflow-y-auto p-4">
        <Outlet />
      </main>
    </div>
  )
}
