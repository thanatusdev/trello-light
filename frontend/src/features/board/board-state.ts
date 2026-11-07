import type { Board } from './api'

/** Pure updates to a cached board, used for optimistic UI. None mutate their input. */

interface TaskMove {
  taskId: string
  toStatusId: string
  /** Index in the target column, counted without the moved task. */
  index: number
  position: number
  /** ISO timestamp used if the move completes the task. */
  now: string
}

export function moveTaskInBoard(board: Board, move: TaskMove): Board {
  const task = board.columns.flatMap((column) => column.tasks).find((t) => t.id === move.taskId)
  const target = board.columns.find((column) => column.id === move.toStatusId)
  if (!task || !target) return board

  // Same rule as the server: entering a done column completes the task (keeping an
  // existing timestamp), leaving one clears it.
  const completedAt = target.is_done ? (task.completed_at ?? move.now) : null
  const moved = {
    ...task,
    status_id: target.id,
    position: move.position,
    completed_at: completedAt,
  }

  return {
    columns: board.columns.map((column) => {
      const tasks = column.tasks.filter((t) => t.id !== move.taskId)
      if (column.id === target.id) tasks.splice(move.index, 0, moved)
      return tasks.length === column.tasks.length && column.id !== target.id
        ? column
        : { ...column, tasks }
    }),
  }
}

interface ColumnMove {
  statusId: string
  /** Index among the columns, counted without the moved column. */
  index: number
  position: number
}

export function moveColumnInBoard(board: Board, move: ColumnMove): Board {
  const column = board.columns.find((c) => c.id === move.statusId)
  if (!column) return board
  const columns = board.columns.filter((c) => c.id !== move.statusId)
  columns.splice(move.index, 0, { ...column, position: move.position })
  return { columns }
}

export function removeTaskFromBoard(board: Board, taskId: string): Board {
  return {
    columns: board.columns.map((column) =>
      column.tasks.some((t) => t.id === taskId)
        ? { ...column, tasks: column.tasks.filter((t) => t.id !== taskId) }
        : column,
    ),
  }
}

/**
 * Where a dragged item ends up in `list` (which already contains it): the slot of the item
 * it is over, or its own slot when over itself, a column, or nothing.
 */
export function landingIndex(list: string[], activeId: string, overId: string | undefined) {
  const overIndex = overId === undefined ? -1 : list.indexOf(overId)
  return overIndex === -1 ? list.indexOf(activeId) : overIndex
}
