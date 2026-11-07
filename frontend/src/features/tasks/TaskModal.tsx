import { Skeleton } from '@/components/ui/skeleton'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { ApiError, errorMessage } from '@/api/errors'
import { useColumns } from '@/features/board/api'
import { useTaskModal } from '@/hooks/use-task-modal'

import { useTask } from './api'
import { TaskForm } from './TaskForm'

/** Create/edit dialog, opened from anywhere by putting `?task=` in the URL. */
export function TaskModal() {
  const { state, close } = useTaskModal()
  const taskId = state.mode === 'edit' ? state.taskId : null
  const taskQuery = useTask(taskId)
  const columnsQuery = useColumns()

  const open = state.mode !== 'closed'
  const loading = columnsQuery.isPending || (taskId !== null && taskQuery.isPending)
  const notFound = taskQuery.error instanceof ApiError && taskQuery.error.status === 404
  const failed = columnsQuery.isError || (taskQuery.isError && !notFound)

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) close()
      }}
    >
      <DialogContent className="max-h-[90svh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{state.mode === 'create' ? 'New task' : 'Edit task'}</DialogTitle>
          <DialogDescription className="sr-only">
            {state.mode === 'create' ? 'Add a task to the board.' : 'Change the task details.'}
          </DialogDescription>
        </DialogHeader>
        {notFound ? (
          <p className="text-muted-foreground">This task no longer exists.</p>
        ) : failed ? (
          <p className="text-destructive">
            Couldn’t load the task. {errorMessage(columnsQuery.error ?? taskQuery.error)} Close this
            and try again.
          </p>
        ) : loading ? (
          <div role="status" aria-label="Loading task" className="flex flex-col gap-4">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-8 w-1/2" />
          </div>
        ) : columnsQuery.data.length === 0 ? (
          <p className="text-muted-foreground">Create a column before adding tasks.</p>
        ) : (
          <TaskForm
            // Remount when switching tasks so the form picks up fresh defaults.
            key={taskId ?? 'new'}
            task={taskQuery.data ?? null}
            columns={columnsQuery.data}
            defaultStatusId={state.mode === 'create' ? state.statusId : null}
            onDone={close}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}
