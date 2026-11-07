import { screen, waitFor } from '@testing-library/react'

import { useAuthStore } from '@/stores/auth-store'
import { useFiltersStore } from '@/stores/filters-store'
import { ids } from '@/test/db'
import { tokens } from '@/test/handlers'
import { renderApp } from '@/test/render'

beforeEach(() => {
  useAuthStore.getState().setTokens(tokens.initial)
})

afterEach(() => {
  useFiltersStore.getState().clear()
})

const params = (search: string) => Object.fromEntries(new URLSearchParams(search))

describe('filter bar', () => {
  it('debounces the search before filtering', async () => {
    const { user, router } = renderApp('/board')

    await user.type(await screen.findByLabelText('Search'), 'schema')
    expect(router.state.location.search).toBe('')

    await waitFor(() => {
      expect(params(router.state.location.search)).toEqual({ search: 'schema' })
    })
    await waitFor(() => {
      expect(screen.queryByText('Write the README')).not.toBeInTheDocument()
    })
    expect(screen.getByText('Design the schema')).toBeInTheDocument()
  })

  it('filters by column, assignee and progress, and clears them all', async () => {
    const { user, router } = renderApp('/tasks')

    await user.click(await screen.findByRole('combobox', { name: 'Column' }))
    await user.click(await screen.findByRole('option', { name: 'To do' }))
    await user.click(screen.getByRole('combobox', { name: 'Assignee' }))
    await user.click(await screen.findByRole('option', { name: 'Alice Smith' }))
    await user.click(screen.getByRole('combobox', { name: 'Progress' }))
    await user.click(await screen.findByRole('option', { name: 'Open' }))

    expect(params(router.state.location.search)).toEqual({
      status_id: ids.todo,
      assignee_id: ids.alice,
      is_completed: 'false',
    })

    await user.click(screen.getByRole('button', { name: 'Clear filters (3)' }))
    expect(router.state.location.search).toBe('')
  })

  it('shows URL filters in the controls and keeps the search box in step', async () => {
    const { user } = renderApp('/board?search=readme&is_completed=true')

    expect(await screen.findByLabelText('Search')).toHaveValue('readme')
    expect(screen.getByRole('combobox', { name: 'Progress' })).toHaveTextContent('Completed')

    await user.click(screen.getByRole('button', { name: 'Clear filters (2)' }))
    expect(screen.getByLabelText('Search')).toHaveValue('')
  })

  it('clears a due date filter', async () => {
    const { user, router } = renderApp('/board?due_after=2026-12-01')

    await user.click(await screen.findByRole('button', { name: 'Clear due from' }))
    expect(router.state.location.search).toBe('')
  })
})
