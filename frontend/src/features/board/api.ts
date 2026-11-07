import { type QueryClient, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { z } from 'zod'

import { apiClient } from '@/api/client'
import { ApiError, errorMessage, toApiError } from '@/api/errors'
import { countActive, type TaskFilters, toQuery } from '@/features/filters/filters'
import { type MoveTaskBody, moveTask, taskKeys, taskSchema } from '@/features/tasks/api'
import { computeMove, toNeighbourIds } from '@/lib/ordering'

import { moveColumnInBoard, moveTaskInBoard } from './board-state'

const columnSchema = z.object({
  id: z.uuid(),
  name: z.string(),
  position: z.number(),
  is_done: z.boolean(),
  tasks: z.array(taskSchema),
})

const boardSchema = z.object({ columns: z.array(columnSchema) })

export type Board = z.infer<typeof boardSchema>
export type Column = z.infer<typeof columnSchema>

export const boardKeys = {
  all: ['board'] as const,
  filtered: (query: TaskFilters) => ['board', query] as const,
}

const moveTaskKey = ['board', 'move-task'] as const
const moveColumnKey = ['board', 'move-column'] as const

/**
 * Rollback and refetch rules shared by overlapping optimistic moves. Inside a mutation's own
 * callbacks it still counts as mutating, so "only one in flight" means `=== 1`.
 *
 * - onError restores the snapshot only when no other move is in flight: that snapshot predates
 *   the other moves, so restoring it would wipe their optimistic state.
 * - onSettled refetches only when the last move settles, so a refetch can't land in between
 *   and briefly undo moves the server hasn't answered yet.
 */
function isLastMove(queryClient: QueryClient, mutationKey: readonly string[]): boolean {
  return queryClient.isMutating({ mutationKey }) === 1
}

/** Board query params: every filter except the status, which the board applies itself. */
export function boardQuery(filters: TaskFilters): TaskFilters {
  return toQuery(filters, { includeStatus: false })
}

export async function fetchBoard(query: TaskFilters): Promise<Board> {
  const { data, error, response } = await apiClient.GET('/api/v1/board', { params: { query } })
  if (!response.ok) throw toApiError(response, error)
  return boardSchema.parse(data)
}

export function useBoard(filters: TaskFilters) {
  const query = boardQuery(filters)
  return useQuery({ queryKey: boardKeys.filtered(query), queryFn: () => fetchBoard(query) })
}

/** Toast for a failed optimistic change that has just been rolled back. */
export function notifyRollback(action: string, error: unknown) {
  if (error instanceof ApiError && error.status === 409) {
    toast.error(`Couldn't ${action}: the board changed elsewhere. It has been refreshed.`)
  } else {
    toast.error(`Couldn't ${action}. ${errorMessage(error)}`)
  }
}

interface MoveTaskVariables {
  taskId: string
  toStatusId: string
  index: number
  position: number
  body: MoveTaskBody
}

/**
 * Drag-and-drop move for a task on the board identified by `filters`. The task jumps to
 * its new place immediately; a failure rolls back and shows a toast. The board is
 * always refetched afterwards so server-side rebalancing is picked up.
 */
export function useMoveTask(filters: TaskFilters) {
  const queryClient = useQueryClient()
  const query = boardQuery(filters)
  const queryKey = boardKeys.filtered(query)

  const mutation = useMutation({
    mutationKey: moveTaskKey,
    mutationFn: ({ taskId, body }: MoveTaskVariables) => moveTask(taskId, body),
    onMutate: async (variables) => {
      await queryClient.cancelQueries({ queryKey: boardKeys.all })
      const previous = queryClient.getQueryData<Board>(queryKey)
      if (previous) {
        queryClient.setQueryData<Board>(
          queryKey,
          moveTaskInBoard(previous, { ...variables, now: new Date().toISOString() }),
        )
      }
      return { previous }
    },
    onError: (error, _variables, context) => {
      if (context?.previous && isLastMove(queryClient, moveTaskKey)) {
        queryClient.setQueryData(queryKey, context.previous)
      }
      notifyRollback('move the task', error)
    },
    onSettled: async () => {
      if (!isLastMove(queryClient, moveTaskKey)) return
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: boardKeys.all }),
        queryClient.invalidateQueries({ queryKey: taskKeys.all }),
      ])
    },
  })

  /**
   * Move `taskId` to `index` of column `toStatusId`, as currently shown. Returns false
   * when there is nothing to do (e.g. the card was dropped back where it was).
   */
  function move(taskId: string, toStatusId: string, index: number): boolean {
    const board = queryClient.getQueryData<Board>(queryKey)
    const target = board?.columns.find((column) => column.id === toStatusId)
    if (!target) return false
    if (target.tasks.findIndex((t) => t.id === taskId) === index) return false
    const plan = computeMove(target.tasks, taskId, index)
    mutation.mutate({
      taskId,
      toStatusId,
      index,
      position: plan.position,
      body: {
        status_id: toStatusId,
        ...toNeighbourIds(plan, { partialView: countActive(query) > 0 }),
      },
    })
    return true
  }

  return { move, isPending: mutation.isPending }
}

export async function moveStatus(
  id: string,
  body: { after_id?: string; before_id?: string },
): Promise<void> {
  const { error, response } = await apiClient.POST('/api/v1/statuses/{status_id}/move', {
    params: { path: { status_id: id } },
    body,
  })
  if (!response.ok) throw toApiError(response, error)
}

interface MoveStatusVariables {
  statusId: string
  index: number
  position: number
  body: { after_id?: string; before_id?: string }
}

/** Optimistic column reorder; same rollback and refetch rules as `useMoveTask`. */
export function useMoveStatus(filters: TaskFilters) {
  const queryClient = useQueryClient()
  const queryKey = boardKeys.filtered(boardQuery(filters))

  const mutation = useMutation({
    mutationKey: moveColumnKey,
    mutationFn: ({ statusId, body }: MoveStatusVariables) => moveStatus(statusId, body),
    onMutate: async (variables) => {
      await queryClient.cancelQueries({ queryKey: boardKeys.all })
      const previous = queryClient.getQueryData<Board>(queryKey)
      if (previous)
        queryClient.setQueryData<Board>(queryKey, moveColumnInBoard(previous, variables))
      return { previous }
    },
    onError: (error, _variables, context) => {
      if (context?.previous && isLastMove(queryClient, moveColumnKey)) {
        queryClient.setQueryData(queryKey, context.previous)
      }
      notifyRollback('move the column', error)
    },
    onSettled: async () => {
      if (isLastMove(queryClient, moveColumnKey)) {
        await queryClient.invalidateQueries({ queryKey: boardKeys.all })
      }
    },
  })

  /** Move column `statusId` to `index` among all columns. Returns false if a no-op. */
  function move(statusId: string, index: number): boolean {
    const columns = queryClient.getQueryData<Board>(queryKey)?.columns ?? []
    const current = columns.findIndex((c) => c.id === statusId)
    if (current === -1 || current === index) return false
    const plan = computeMove(columns, statusId, index)
    // Columns are never filtered out of the board response, so both neighbours are safe.
    mutation.mutate({
      statusId,
      index,
      position: plan.position,
      body: toNeighbourIds(plan, { partialView: false }),
    })
    return true
  }

  return { move, isPending: mutation.isPending }
}

export type ColumnSummary = Omit<Column, 'tasks'>

/**
 * The board's columns, without tasks. There is no `GET /statuses`, so this reads the
 * unfiltered board (shared with the board page when no filters are active).
 */
export function useColumns() {
  return useQuery({
    queryKey: boardKeys.filtered({}),
    queryFn: () => fetchBoard({}),
    select: (board): ColumnSummary[] => board.columns.map(({ tasks: _tasks, ...column }) => column),
  })
}
