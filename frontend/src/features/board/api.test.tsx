import { QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import type { ReactNode } from 'react'
import { toast } from 'sonner'

import { createQueryClient } from '@/app/query-client'
import type { TaskFilters } from '@/features/filters/filters'
import { useAuthStore } from '@/stores/auth-store'
import { useDeleteTask } from '@/features/tasks/mutations'
import { db, ids } from '@/test/db'
import { API, tokens } from '@/test/handlers'
import { server } from '@/test/server'

import {
  type Board,
  boardKeys,
  boardQuery,
  fetchBoard,
  useBoard,
  useMoveStatus,
  useMoveTask,
} from './api'

/** Also observe the board, as BoardPage does, so invalidation refetches it. */
function withBoard<T>(useMove: (filters: TaskFilters) => T) {
  return (filters: TaskFilters) => {
    useBoard(filters)
    return useMove(filters)
  }
}

vi.mock('sonner', async (importOriginal) => {
  const actual = await importOriginal<typeof import('sonner')>()
  return { ...actual, toast: { error: vi.fn(), success: vi.fn() } }
})

async function setup<T>(useHook: (filters: TaskFilters) => T, filters: TaskFilters = {}) {
  useAuthStore.getState().setTokens(tokens.initial)
  const queryClient = createQueryClient({ retry: false })
  const key = boardKeys.filtered(boardQuery(filters))
  queryClient.setQueryData(key, await fetchBoard(boardQuery(filters)))
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  const { result } = renderHook(() => useHook(filters), { wrapper })
  const board = () => queryClient.getQueryData<Board>(key)
  const titles = (statusId: string) =>
    board()
      ?.columns.find((c) => c.id === statusId)
      ?.tasks.map((t) => t.title)
  return { result, board, titles }
}

/** Capture the body of the next request to a move endpoint. */
function captureMove(path: string) {
  const bodies: unknown[] = []
  server.events.on('request:start', ({ request }) => {
    if (request.method === 'POST' && new URL(request.url).pathname.endsWith(path)) {
      void request
        .clone()
        .json()
        .then((body: unknown) => bodies.push(body))
    }
  })
  return bodies
}

/**
 * Hold requests to `path` until `release()` so a test can see the optimistic state
 * before the server answers. Requests pass through to the default handlers afterwards.
 */
function gate(method: 'post', path: string) {
  let release: () => void = () => undefined
  const opened = new Promise<void>((resolve) => {
    release = resolve
  })
  server.use(
    http[method](`${API}${path}`, async () => {
      await opened
      return undefined
    }),
  )
  return { release }
}

describe('useMoveTask', () => {
  it('moves the card immediately and sends both neighbours', async () => {
    const bodies = captureMove('/move')
    const { release } = gate('post', '/tasks/:id/move')
    const { result, titles } = await setup(useMoveTask)

    act(() => {
      result.current.move(ids.schema, ids.todo, 0)
    })

    await waitFor(() => {
      expect(titles(ids.todo)).toEqual(['Design the schema', 'Write the README'])
    })
    release()
    await waitFor(() => {
      expect(bodies).toEqual([{ status_id: ids.todo, before_id: ids.readme }])
    })
    await waitFor(() => {
      expect(db.tasks.find((t) => t.id === ids.schema)?.position).toBe(512)
    })
  })

  it('completes the card optimistically when it is dropped in a done column', async () => {
    const { release } = gate('post', '/tasks/:id/move')
    const { result, board } = await setup(useMoveTask)

    act(() => {
      result.current.move(ids.readme, ids.done, 1)
    })

    await waitFor(() => {
      expect(board()?.columns[2]?.tasks[1]).toMatchObject({ id: ids.readme, status_id: ids.done })
    })
    expect(board()?.columns[2]?.tasks[1]?.completed_at).not.toBeNull()
    release()
    await waitFor(() => {
      expect(result.current.isPending).toBe(false)
    })
  })

  it('anchors on a single neighbour when the board is filtered', async () => {
    const bodies = captureMove('/move')
    // Both todo cards match the search, so the visible list equals the full one here;
    // the request must still use one neighbour because the view is filtered.
    const { result } = await setup(useMoveTask, { search: 'e' })

    act(() => {
      result.current.move(ids.readme, ids.todo, 1)
    })

    await waitFor(() => {
      expect(bodies).toEqual([{ status_id: ids.todo, after_id: ids.schema }])
    })
  })

  it('does nothing when a card is dropped where it was', async () => {
    const bodies = captureMove('/move')
    const { result } = await setup(useMoveTask)

    act(() => {
      result.current.move(ids.readme, ids.todo, 0)
    })

    expect(result.current.isPending).toBe(false)
    expect(bodies).toEqual([])
  })

  it('rolls back and explains when the server rejects the move', async () => {
    let fail: () => void = () => undefined
    const failed = new Promise<void>((resolve) => {
      fail = resolve
    })
    server.use(
      http.post(`${API}/tasks/:id/move`, async () => {
        await failed
        return HttpResponse.json({ detail: 'Database is down' }, { status: 500 })
      }),
    )
    const { result, titles } = await setup(useMoveTask)

    act(() => {
      result.current.move(ids.readme, ids.doing, 0)
    })
    await waitFor(() => {
      expect(titles(ids.doing)).toEqual(['Write the README'])
    })
    fail()

    await waitFor(() => {
      expect(titles(ids.doing)).toEqual([])
    })
    expect(titles(ids.todo)).toEqual(['Write the README', 'Design the schema'])
    expect(toast.error).toHaveBeenCalledWith("Couldn't move the task. Database is down")
  })

  it('says how long to wait when the move is rate limited', async () => {
    server.use(
      http.post(`${API}/tasks/:id/move`, () =>
        HttpResponse.json(
          { detail: 'Rate limit exceeded' },
          { status: 429, headers: { 'Retry-After': '20' } },
        ),
      ),
    )
    const { result } = await setup(useMoveTask)

    act(() => {
      result.current.move(ids.readme, ids.doing, 0)
    })

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        "Couldn't move the task. Too many requests. Try again in 20 seconds.",
      )
    })
  })

  it("does not undo a later move's optimistic state when an earlier overlapping move fails", async () => {
    let failFirst: () => void = () => undefined
    let finishSecond: () => void = () => undefined
    const first = new Promise<void>((resolve) => {
      failFirst = resolve
    })
    const second = new Promise<void>((resolve) => {
      finishSecond = resolve
    })
    server.use(
      http.post(`${API}/tasks/:id/move`, async ({ params }) => {
        if (params.id === ids.readme) {
          await first
          return HttpResponse.json({ detail: 'Database is down' }, { status: 500 })
        }
        await second
        return undefined
      }),
    )
    const { result, titles } = await setup(withBoard(useMoveTask))

    act(() => {
      result.current.move(ids.readme, ids.doing, 0)
    })
    await waitFor(() => {
      expect(titles(ids.doing)).toEqual(['Write the README'])
    })
    act(() => {
      result.current.move(ids.schema, ids.done, 0)
    })
    await waitFor(() => {
      expect(titles(ids.done)).toEqual(['Design the schema', 'Ship it'])
    })

    failFirst()
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Couldn't move the task. Database is down")
    })
    // The second move is still in flight: its card must stay where the user put it.
    expect(titles(ids.done)).toEqual(['Design the schema', 'Ship it'])

    finishSecond()
    // Once everything settles the board is refetched: the failed move is undone for real.
    await waitFor(() => {
      expect(titles(ids.doing)).toEqual([])
    })
    expect(titles(ids.todo)).toEqual(['Write the README'])
    expect(titles(ids.done)).toEqual(['Design the schema', 'Ship it'])
  })

  it('tells the user the board changed when the order was stale', async () => {
    const { result } = await setup(useMoveTask)
    // Someone else deleted the neighbour we are about to anchor on.
    db.tasks = db.tasks.filter((t) => t.id !== ids.readme)

    act(() => {
      result.current.move(ids.schema, ids.todo, 0)
    })

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        "Couldn't move the task: the board changed elsewhere. It has been refreshed.",
      )
    })
  })
})

describe('useMoveStatus', () => {
  const names = (board: Board | undefined) => board?.columns.map((c) => c.name)

  it('reorders columns immediately and persists the move', async () => {
    const bodies = captureMove('/move')
    const { release } = gate('post', '/statuses/:id/move')
    const { result, board } = await setup(useMoveStatus)

    act(() => {
      result.current.move(ids.done, 0)
    })

    await waitFor(() => {
      expect(names(board())).toEqual(['Done', 'To do', 'Doing'])
    })
    release()
    await waitFor(() => {
      expect(bodies).toEqual([{ before_id: ids.todo }])
    })
  })

  it('ignores a column dropped in place', async () => {
    const { result } = await setup(useMoveStatus)
    act(() => {
      result.current.move(ids.doing, 1)
    })
    expect(result.current.isPending).toBe(false)
  })

  it('does not undo a later column move when an earlier overlapping one fails', async () => {
    let failFirst: () => void = () => undefined
    let finishSecond: () => void = () => undefined
    const first = new Promise<void>((resolve) => {
      failFirst = resolve
    })
    const second = new Promise<void>((resolve) => {
      finishSecond = resolve
    })
    server.use(
      http.post(`${API}/statuses/:id/move`, async ({ params }) => {
        if (params.id === ids.todo) {
          await first
          return HttpResponse.json({ detail: 'nope' }, { status: 500 })
        }
        await second
        return undefined
      }),
    )
    const { result, board } = await setup(withBoard(useMoveStatus))

    act(() => {
      result.current.move(ids.todo, 2)
    })
    await waitFor(() => {
      expect(names(board())).toEqual(['Doing', 'Done', 'To do'])
    })
    act(() => {
      result.current.move(ids.done, 0)
    })
    await waitFor(() => {
      expect(names(board())).toEqual(['Done', 'Doing', 'To do'])
    })

    failFirst()
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Couldn't move the column. nope")
    })
    expect(names(board())).toEqual(['Done', 'Doing', 'To do'])

    finishSecond()
    // Refetched: "To do" never moved; "Done" landed before "Doing", as the user asked.
    await waitFor(() => {
      expect(names(board())).toEqual(['To do', 'Done', 'Doing'])
    })
  })

  it('rolls back on failure', async () => {
    server.use(
      http.post(`${API}/statuses/:id/move`, () =>
        HttpResponse.json({ detail: 'nope' }, { status: 500 }),
      ),
    )
    const { result, board } = await setup(useMoveStatus)

    act(() => {
      result.current.move(ids.todo, 2)
    })

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Couldn't move the column. nope")
    })
    expect(names(board())).toEqual(['To do', 'Doing', 'Done'])
  })
})

describe('overlapping board changes', () => {
  const names = (board: Board | undefined) => board?.columns.map((c) => c.name)

  function useBoardActions(filters: TaskFilters) {
    useBoard(filters)
    return {
      task: useMoveTask(filters),
      column: useMoveStatus(filters),
      remove: useDeleteTask(),
    }
  }

  /** Requests started against move endpoints, in order. */
  function startedMoves() {
    const started: string[] = []
    server.events.on('request:start', ({ request }) => {
      if (request.method === 'POST' && request.url.endsWith('/move')) {
        started.push(new URL(request.url).pathname)
      }
    })
    return started
  }

  it('sends a second move only after the first one has been answered', async () => {
    const started = startedMoves()
    const { release } = gate('post', '/tasks/:id/move')
    const { result, board, titles } = await setup(useBoardActions)

    act(() => {
      result.current.task.move(ids.readme, ids.doing, 0)
    })
    act(() => {
      result.current.column.move(ids.done, 0)
    })

    // Both changes show at once, but only the first request is on the wire.
    await waitFor(() => {
      expect(titles(ids.doing)).toEqual(['Write the README'])
    })
    await waitFor(() => {
      expect(started).toHaveLength(1)
    })
    expect(started[0]).toContain(`/tasks/${ids.readme}/move`)

    release()
    await waitFor(() => {
      expect(started).toHaveLength(2)
    })
    expect(started[1]).toContain(`/statuses/${ids.done}/move`)
    // Each request was computed against the committed result of the one before it.
    await waitFor(() => {
      expect(names(board())).toEqual(['Done', 'To do', 'Doing'])
    })
    expect(titles(ids.doing)).toEqual(['Write the README'])
  })

  it('does not undo a pending column move when a task move fails', async () => {
    let fail: () => void = () => undefined
    const failed = new Promise<void>((resolve) => {
      fail = resolve
    })
    server.use(
      http.post(`${API}/tasks/:id/move`, async () => {
        await failed
        return HttpResponse.json({ detail: 'Database is down' }, { status: 500 })
      }),
    )
    const { release } = gate('post', '/statuses/:id/move')
    const { result, board } = await setup(useBoardActions)

    act(() => {
      result.current.task.move(ids.readme, ids.doing, 0)
    })
    act(() => {
      result.current.column.move(ids.done, 0)
    })
    await waitFor(() => {
      expect(names(board())).toEqual(['Done', 'To do', 'Doing'])
    })

    fail()
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Couldn't move the task. Database is down")
    })
    // The column move hasn't been answered yet: it must stay where the user put it.
    expect(names(board())).toEqual(['Done', 'To do', 'Doing'])

    release()
    await waitFor(() => {
      expect(result.current.column.isPending).toBe(false)
    })
    await waitFor(() => {
      expect(names(board())).toEqual(['Done', 'To do', 'Doing'])
    })
  })

  it('does not undo a pending move when a delete fails', async () => {
    const { release } = gate('post', '/tasks/:id/move')
    server.use(
      http.delete(`${API}/tasks/:id`, () =>
        HttpResponse.json({ detail: 'Database is down' }, { status: 500 }),
      ),
    )
    const { result, titles } = await setup(useBoardActions)

    act(() => {
      result.current.task.move(ids.readme, ids.doing, 0)
    })
    await waitFor(() => {
      expect(titles(ids.doing)).toEqual(['Write the README'])
    })

    await act(async () => {
      await result.current.remove.mutateAsync(ids.ship).catch(() => undefined)
    })
    expect(toast.error).toHaveBeenCalledWith("Couldn't delete the task. Database is down")
    expect(titles(ids.doing)).toEqual(['Write the README'])

    release()
    await waitFor(() => {
      expect(result.current.task.isPending).toBe(false)
    })
    await waitFor(() => {
      expect(titles(ids.done)).toEqual(['Ship it'])
    })
    expect(titles(ids.doing)).toEqual(['Write the README'])
  })
})
