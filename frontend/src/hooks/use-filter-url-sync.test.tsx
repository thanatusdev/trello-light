import { act, render } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'

import { useFiltersStore } from '@/stores/filters-store'

import { useFilterUrlSync } from './use-filter-url-sync'

const USER = '6f1c2a3e-0000-4000-8000-000000000001'

function Sync() {
  useFilterUrlSync()
  return null
}

function setup(entry: string) {
  const router = createMemoryRouter([{ path: '/board', element: <Sync /> }], {
    initialEntries: [entry],
  })
  render(<RouterProvider router={router} />)
  return router
}

const search = (router: ReturnType<typeof setup>) =>
  Object.fromEntries(new URLSearchParams(router.state.location.search))

afterEach(() => {
  useFiltersStore.getState().clear()
})

describe('useFilterUrlSync', () => {
  it('loads filters from the URL into the store', () => {
    setup(`/board?assignee_id=${USER}&is_completed=true&status_id=bad`)
    expect(useFiltersStore.getState().filters).toEqual({ assignee_id: USER, is_completed: true })
  })

  it('does not wipe URL filters on first load', () => {
    const router = setup('/board?search=readme')
    expect(search(router)).toEqual({ search: 'readme' })
  })

  it('writes store changes back to the URL, replacing history and resetting the page', () => {
    const router = setup('/board?page=4&task=abc')
    const historyBefore = router.state.historyAction

    act(() => {
      useFiltersStore.getState().setFilter('search', 'docs')
    })

    expect(search(router)).toEqual({ task: 'abc', search: 'docs' })
    expect(router.state.historyAction).toBe('REPLACE')
    expect(historyBefore).toBe('POP')
  })

  it('follows the URL when it changes, e.g. on back/forward', async () => {
    const router = setup('/board?search=one')
    await act(() => router.navigate('/board?search=two'))
    expect(useFiltersStore.getState().filters).toEqual({ search: 'two' })
  })

  it('clears the URL filters when the store is cleared', () => {
    const router = setup(`/board?assignee_id=${USER}&size=50`)
    act(() => {
      useFiltersStore.getState().clear()
    })
    expect(search(router)).toEqual({ size: '50' })
  })
})
