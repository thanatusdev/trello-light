import { screen, waitFor, within } from '@testing-library/react'

import { useAuthStore } from '@/stores/auth-store'
import { db, ids, makeTask } from '@/test/db'
import { tokens } from '@/test/handlers'
import { renderApp } from '@/test/render'

import { parsePaging } from './paging'

beforeEach(() => {
  useAuthStore.getState().setTokens(tokens.initial)
})

/** 25 tasks, newest first: "Task 25" … "Task 01". */
function seedMany() {
  db.tasks = Array.from({ length: 25 }, (_, i) =>
    makeTask({
      id: `7a5c0000-0000-4000-8000-${String(500 + i).padStart(12, '0')}`,
      title: `Task ${String(i + 1).padStart(2, '0')}`,
      status_id: ids.todo,
      position: 1024 * (i + 1),
      created_at: `2026-11-01T10:${String(i).padStart(2, '0')}:00Z`,
    }),
  )
}

const tableTitles = () =>
  within(screen.getByRole('table'))
    .getAllByRole('row')
    .slice(1)
    .map((row) => within(row).getAllByRole('cell')[0]?.textContent)

describe('task list', () => {
  it('lists tasks with their column, assignee and dates', async () => {
    renderApp('/tasks')

    const row = await screen.findByRole('row', { name: /Write the README/ })
    const cells = within(row)
      .getAllByRole('cell')
      .map((c) => c.textContent)
    expect(cells).toEqual(['Write the README', 'To do', 'Alice Smith', 'Jan 31, 2030', '—'])
  })

  it('pages through results, keeping page and size in the URL', async () => {
    seedMany()
    const { user, router } = renderApp('/tasks?size=10')

    await screen.findByRole('table')
    expect(tableTitles()).toHaveLength(10)
    expect(tableTitles()[0]).toBe('Task 25')
    expect(screen.getByText('Page 1 of 3 · 25 tasks')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous page' })).toBeDisabled()

    await user.click(screen.getByRole('button', { name: 'Next page' }))
    await waitFor(() => {
      expect(tableTitles()[0]).toBe('Task 15')
    })
    expect(new URLSearchParams(router.state.location.search).get('page')).toBe('2')

    await user.click(screen.getByRole('button', { name: 'Next page' }))
    await waitFor(() => {
      expect(tableTitles()).toHaveLength(5)
    })
    expect(screen.getByRole('button', { name: 'Next page' })).toBeDisabled()
  })

  it('changes the page size and goes back to the first page', async () => {
    seedMany()
    const { user, router } = renderApp('/tasks?size=10&page=2')

    await screen.findByText('Page 2 of 3 · 25 tasks')
    await user.click(screen.getByRole('combobox', { name: 'Per page' }))
    await user.click(await screen.findByRole('option', { name: '50' }))

    expect(await screen.findByText('Page 1 of 1 · 25 tasks')).toBeInTheDocument()
    const params = new URLSearchParams(router.state.location.search)
    expect(params.get('size')).toBe('50')
    expect(params.has('page')).toBe(false)
  })

  it('applies the filters from the URL', async () => {
    renderApp('/tasks?is_completed=true')

    await screen.findByRole('table')
    expect(tableTitles()).toEqual(['Ship it'])
  })

  it('offers the first page when the current one is past the end', async () => {
    const { user } = renderApp('/tasks?page=9')

    await user.click(await screen.findByRole('button', { name: 'Go to the first page' }))
    expect(await screen.findByRole('table')).toBeInTheDocument()
  })

  it('shows an empty state with a way to clear filters', async () => {
    const { user } = renderApp('/tasks?search=nothing-like-this')

    expect(await screen.findByText('No tasks match these filters.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Clear filters' }))
    expect(await screen.findByRole('table')).toBeInTheDocument()
  })

  it('says when there are no tasks at all', async () => {
    db.tasks = []
    renderApp('/tasks')
    expect(await screen.findByText('No tasks yet.')).toBeInTheDocument()
  })

  it('opens a task from its row', async () => {
    const { user, router } = renderApp('/tasks')

    await user.click(
      await within(await screen.findByRole('table')).findByRole('button', { name: 'Ship it' }),
    )

    expect(new URLSearchParams(router.state.location.search).get('task')).toBe(ids.ship)
    expect(await screen.findByRole('dialog', { name: 'Edit task' })).toBeInTheDocument()
  })

  it('keeps filters but drops the page when switching to the board', async () => {
    const { user, router } = renderApp('/tasks?search=Ship&page=1')

    await screen.findByRole('table')
    await user.click(screen.getByRole('link', { name: 'Board' }))

    expect(router.state.location.pathname).toBe('/board')
    expect(router.state.location.search).toBe('?search=Ship')
  })
})

describe('parsePaging', () => {
  it('falls back to page 1 and size 20 for invalid values', () => {
    expect(parsePaging(new URLSearchParams('page=-1&size=7'))).toEqual({ page: 1, size: 20 })
    expect(parsePaging(new URLSearchParams('page=3&size=50'))).toEqual({ page: 3, size: 50 })
  })
})
