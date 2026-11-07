import { PlusIcon } from 'lucide-react'
import { Outlet } from 'react-router'

import { Button } from '@/components/ui/button'
import { FilterBar } from '@/features/filters/FilterBar'
import { TaskModal } from '@/features/tasks/TaskModal'
import { useFilterUrlSync } from '@/hooks/use-filter-url-sync'
import { useTaskModal } from '@/hooks/use-task-modal'

/** Shared chrome for the board and list views: filters, "New task" and the task modal. */
export function WorkspaceLayout() {
  useFilterUrlSync()
  const { openNew } = useTaskModal()

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <FilterBar />
        <Button
          className="self-start lg:self-end"
          onClick={() => {
            openNew()
          }}
        >
          <PlusIcon aria-hidden />
          New task
        </Button>
      </div>
      <div className="min-h-0 flex-1">
        <Outlet />
      </div>
      <TaskModal />
    </div>
  )
}
