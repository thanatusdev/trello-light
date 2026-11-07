import { useCallback } from 'react'
import { useSearchParams } from 'react-router'

export type TaskModalState =
  | { mode: 'closed' }
  | { mode: 'create'; statusId: string | null }
  | { mode: 'edit'; taskId: string }

/**
 * The task modal lives in the URL (`?task=<id>` or `?task=new&status=<id>`), so a task
 * can be linked to and the browser's Back button closes it.
 */
export function useTaskModal() {
  const [searchParams, setSearchParams] = useSearchParams()
  const task = searchParams.get('task')
  const state: TaskModalState =
    task === null
      ? { mode: 'closed' }
      : task === 'new'
        ? { mode: 'create', statusId: searchParams.get('status') }
        : { mode: 'edit', taskId: task }

  const openTask = useCallback(
    (taskId: string) => {
      setSearchParams((previous) => {
        const next = new URLSearchParams(previous)
        next.set('task', taskId)
        next.delete('status')
        return next
      })
    },
    [setSearchParams],
  )

  const openNew = useCallback(
    (statusId?: string) => {
      setSearchParams((previous) => {
        const next = new URLSearchParams(previous)
        next.set('task', 'new')
        if (statusId) next.set('status', statusId)
        else next.delete('status')
        return next
      })
    },
    [setSearchParams],
  )

  const close = useCallback(() => {
    setSearchParams(
      (previous) => {
        const next = new URLSearchParams(previous)
        next.delete('task')
        next.delete('status')
        return next
      },
      { replace: true },
    )
  }, [setSearchParams])

  return { state, openTask, openNew, close }
}
