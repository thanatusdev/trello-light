import { hashKey, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { type Board, boardKeys, notifyRollback } from '@/features/board/api'
import { removeTaskFromBoard } from '@/features/board/board-state'

import {
  assignTask,
  createTask,
  deleteTask,
  moveTask,
  type Task,
  taskKeys,
  type UpdateTaskBody,
  updateTask,
} from './api'
import type { TaskFormValues } from './schema'

export interface SaveTaskInput {
  /** The task being edited, or null to create one. */
  original: Task | null
  values: TaskFormValues
  /** Column to move the task to (bottom), e.g. after toggling "complete". */
  moveToStatusId?: string | null
}

/** The fields of a PATCH body that actually changed. */
export function changedFields(original: Task, values: TaskFormValues): UpdateTaskBody {
  const body: UpdateTaskBody = {}
  if (values.title !== original.title) body.title = values.title
  if (values.description !== original.description) body.description = values.description
  if (values.due_date !== original.due_date) body.due_date = values.due_date
  return body
}

/**
 * Persist the task form. Editing calls only the endpoints whose data changed, in order:
 * fields (PATCH), assignee (PUT), then column (move). Returns the task id.
 */
export async function saveTask({ original, values, moveToStatusId }: SaveTaskInput) {
  if (!original) return (await createTask(values)).id

  const fields = changedFields(original, values)
  if (Object.keys(fields).length > 0) await updateTask(original.id, fields)
  if (values.assignee_id !== (original.assignee?.id ?? null)) {
    await assignTask(original.id, values.assignee_id)
  }
  if (moveToStatusId && moveToStatusId !== original.status_id) {
    await moveTask(original.id, { status_id: moveToStatusId })
  }
  return original.id
}

function useInvalidateTasks() {
  const queryClient = useQueryClient()
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: boardKeys.all }),
      queryClient.invalidateQueries({ queryKey: taskKeys.all }),
    ])
}

/** Not optimistic: the modal stays open and shows the server's error inline. */
export function useSaveTask() {
  const invalidate = useInvalidateTasks()
  // Refetch even after a failure: an edit may have partly succeeded.
  return useMutation({ mutationFn: saveTask, onSettled: invalidate })
}

/** Removes the task from every cached board at once; rolls back with a toast on failure. */
export function useDeleteTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteTask,
    onMutate: async (taskId) => {
      await queryClient.cancelQueries({ queryKey: boardKeys.all })
      const previous = queryClient.getQueriesData<Board>({ queryKey: boardKeys.all })
      queryClient.setQueriesData<Board>({ queryKey: boardKeys.all }, (board) =>
        board ? removeTaskFromBoard(board, taskId) : board,
      )
      return { previous }
    },
    onError: (error, _taskId, context) => {
      for (const [key, board] of context?.previous ?? []) queryClient.setQueryData(key, board)
      notifyRollback('delete the task', error)
    },
    onSuccess: () => {
      toast.success('Task deleted.')
    },
    onSettled: (_data, error, taskId) => {
      // Once it's gone, refetching the task itself (the edit modal may still be closing)
      // can only 404; refresh everything else.
      const gone = error ? null : hashKey(taskKeys.detail(taskId))
      return Promise.all([
        queryClient.invalidateQueries({ queryKey: boardKeys.all }),
        queryClient.invalidateQueries({
          queryKey: taskKeys.all,
          predicate: (query) => query.queryHash !== gone,
        }),
      ])
    },
  })
}
