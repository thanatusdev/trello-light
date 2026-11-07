import type { ColumnSummary } from '@/features/board/api'

/**
 * Where "Mark complete" sends a task: the left-most done column, or back to the
 * left-most open column when unticked. The API completes tasks only via their column.
 */
export function completionTarget(columns: ColumnSummary[], complete: boolean) {
  return columns.find((column) => column.is_done === complete) ?? null
}
