import type { Board } from './api'
import {
  landingIndex,
  moveColumnInBoard,
  moveTaskInBoard,
  removeTaskFromBoard,
} from './board-state'

const NOW = '2026-11-06T12:00:00.000Z'

function task(id: string, statusId: string, position: number, completedAt: string | null = null) {
  return {
    id,
    title: id,
    description: null,
    status_id: statusId,
    assignee: null,
    created_by_id: 'u',
    due_date: null,
    position,
    completed_at: completedAt,
    created_at: NOW,
    updated_at: NOW,
  }
}

function makeBoard(): Board {
  return {
    columns: [
      {
        id: 'todo',
        name: 'To do',
        position: 1024,
        is_done: false,
        tasks: [task('a', 'todo', 1024), task('b', 'todo', 2048), task('c', 'todo', 3072)],
      },
      { id: 'doing', name: 'Doing', position: 2048, is_done: false, tasks: [] },
      {
        id: 'done',
        name: 'Done',
        position: 3072,
        is_done: true,
        tasks: [task('d', 'done', 1024, '2026-11-01T00:00:00Z')],
      },
    ],
  }
}

const ids = (board: Board, columnId: string) =>
  board.columns.find((c) => c.id === columnId)?.tasks.map((t) => t.id)

describe('moveTaskInBoard', () => {
  it('reorders within a column', () => {
    const next = moveTaskInBoard(makeBoard(), {
      taskId: 'a',
      toStatusId: 'todo',
      index: 2,
      position: 4096,
      now: NOW,
    })
    expect(ids(next, 'todo')).toEqual(['b', 'c', 'a'])
    expect(next.columns[0]?.tasks[2]?.position).toBe(4096)
  })

  it('moves across columns, updating the status', () => {
    const next = moveTaskInBoard(makeBoard(), {
      taskId: 'b',
      toStatusId: 'doing',
      index: 0,
      position: 1024,
      now: NOW,
    })
    expect(ids(next, 'todo')).toEqual(['a', 'c'])
    expect(next.columns[1]?.tasks[0]).toMatchObject({ id: 'b', status_id: 'doing' })
  })

  it('marks a task completed when it enters a done column', () => {
    const next = moveTaskInBoard(makeBoard(), {
      taskId: 'a',
      toStatusId: 'done',
      index: 0,
      position: 512,
      now: NOW,
    })
    expect(ids(next, 'done')).toEqual(['a', 'd'])
    expect(next.columns[2]?.tasks[0]?.completed_at).toBe(NOW)
  })

  it('clears completion when a task leaves a done column', () => {
    const next = moveTaskInBoard(makeBoard(), {
      taskId: 'd',
      toStatusId: 'doing',
      index: 0,
      position: 1024,
      now: NOW,
    })
    expect(next.columns[1]?.tasks[0]?.completed_at).toBeNull()
  })

  it('does not mutate the original board', () => {
    const board = makeBoard()
    moveTaskInBoard(board, { taskId: 'a', toStatusId: 'doing', index: 0, position: 1, now: NOW })
    expect(ids(board, 'todo')).toEqual(['a', 'b', 'c'])
  })

  it('returns the board unchanged for an unknown task or column', () => {
    const board = makeBoard()
    const args = { index: 0, position: 1, now: NOW }
    expect(moveTaskInBoard(board, { ...args, taskId: 'zzz', toStatusId: 'doing' })).toBe(board)
    expect(moveTaskInBoard(board, { ...args, taskId: 'a', toStatusId: 'zzz' })).toBe(board)
  })
})

describe('moveColumnInBoard', () => {
  it('reorders columns', () => {
    const next = moveColumnInBoard(makeBoard(), { statusId: 'done', index: 0, position: 512 })
    expect(next.columns.map((c) => c.id)).toEqual(['done', 'todo', 'doing'])
    expect(next.columns[0]?.position).toBe(512)
  })

  it('returns the board unchanged for an unknown column', () => {
    const board = makeBoard()
    expect(moveColumnInBoard(board, { statusId: 'zzz', index: 0, position: 1 })).toBe(board)
  })
})

describe('removeTaskFromBoard', () => {
  it('removes the task from its column', () => {
    expect(ids(removeTaskFromBoard(makeBoard(), 'b'), 'todo')).toEqual(['a', 'c'])
  })
})

describe('landingIndex', () => {
  const list = ['a', 'b', 'c']

  it('is the index of the item the dragged one is over', () => {
    expect(landingIndex(list, 'c', 'a')).toBe(0)
    expect(landingIndex(list, 'a', 'b')).toBe(1)
  })

  it('stays put when over itself or over something outside the list', () => {
    expect(landingIndex(list, 'b', 'b')).toBe(1)
    expect(landingIndex(list, 'b', 'column:x')).toBe(1)
    expect(landingIndex(list, 'b', undefined)).toBe(1)
  })
})
