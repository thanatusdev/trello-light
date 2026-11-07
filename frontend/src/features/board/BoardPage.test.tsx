import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { toast } from 'sonner'

import { useAuthStore } from '@/stores/auth-store'
import { db, ids } from '@/test/db'
import { API, tokens } from '@/test/handlers'
import { renderApp } from '@/test/render'
import { recordRequests } from '@/test/requests'
import { server } from '@/test/server'

vi.mock('sonner', async (importOriginal) => {
  const actual = await importOriginal<typeof import('sonner')>()
  return { ...actual, toast: { error: vi.fn(), success: vi.fn() } }
})

function signIn() {
  useAuthStore.getState().setTokens(tokens.initial)
}

const column = (name: string) => screen.findByRole('region', { name })

describe('board page', () => {
  beforeEach(signIn)

  it('redirects the home page to the board and shows columns with their tasks', async () => {
    const { router } = renderApp('/')

    expect(screen.getByRole('status', { name: /loading/i })).toBeInTheDocument()
    const todo = await column('To do')
    expect(router.state.location.pathname).toBe('/board')
    expect(
      within(todo)
        .getAllByRole('listitem')
        .map((li) => li.textContent),
    ).toEqual([
      expect.stringContaining('Write the README'),
      expect.stringContaining('Design the schema'),
    ])
    expect(within(await column('Doing')).getByText('No tasks yet')).toBeInTheDocument()
    expect(within(await column('Done')).getByText('Ship it')).toBeInTheDocument()
  })

  it('shows an error with a retry when the board fails to load', async () => {
    let fail = true
    server.use(
      http.get(`${API}/board`, () =>
        fail ? HttpResponse.json({ detail: 'Board unavailable' }, { status: 500 }) : undefined,
      ),
    )
    const { user } = renderApp('/board')

    expect(await screen.findByText(/Board unavailable/)).toBeInTheDocument()
    fail = false
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await column('To do')).toBeInTheDocument()
  })

  it('says how long to wait when loading the board is rate limited', async () => {
    server.use(
      http.get(`${API}/board`, () =>
        HttpResponse.json(
          { detail: 'Rate limit exceeded' },
          { status: 429, headers: { 'Retry-After': '9' } },
        ),
      ),
    )
    renderApp('/board')

    expect(
      await screen.findByText(
        'Couldn’t load the board. Too many requests. Try again in 9 seconds.',
      ),
    ).toBeInTheDocument()
  })

  it('applies filters from the URL and offers to clear them when nothing matches', async () => {
    const { user, router } = renderApp('/board?search=zzz')

    expect(await screen.findByText('No tasks match these filters.')).toBeInTheDocument()
    expect(within(await column('To do')).getByText('No matching tasks')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Clear filters' }))

    expect(await screen.findByText('Write the README')).toBeInTheDocument()
    expect(router.state.location.search).toBe('')
  })

  it('shows only the filtered column and turns off column reordering', async () => {
    renderApp(`/board?status_id=${ids.done}`)

    expect(await column('Done')).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'To do' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Move column/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Add column' })).not.toBeInTheDocument()
  })

  it('opens a task in the modal from its card', async () => {
    const { user, router } = renderApp('/board')

    await user.click(await screen.findByRole('button', { name: 'Open Write the README' }))

    expect(router.state.location.search).toBe(`?task=${ids.readme}`)
    expect(await screen.findByRole('dialog', { name: 'Edit task' })).toBeInTheDocument()
    expect(await screen.findByDisplayValue('Write the README')).toBeInTheDocument()
  })

  it('opens the new-task modal for a specific column', async () => {
    const { user, router } = renderApp('/board')

    await user.click(await screen.findByRole('button', { name: 'Add task to Doing' }))

    expect(router.state.location.search).toBe(`?task=new&status=${ids.doing}`)
    expect(await screen.findByRole('dialog', { name: 'New task' })).toBeInTheDocument()
  })

  it('moves a task with the keyboard', async () => {
    const requests = recordRequests()
    const { user } = renderApp('/board')

    const handle = await screen.findByRole('button', { name: 'Move Design the schema' })
    handle.focus()
    await user.keyboard(' ')
    await user.keyboard('{ArrowUp}')
    await user.keyboard(' ')

    await waitFor(() => {
      expect(requests).toEqual([
        expect.objectContaining({ method: 'POST', path: `/tasks/${ids.schema}/move` }),
      ])
    })
  })
})

describe('columns', () => {
  beforeEach(signIn)

  it('creates a column, rejecting a blank or duplicate name inline', async () => {
    const { user } = renderApp('/board')

    await user.click(await screen.findByRole('button', { name: 'Add column' }))
    const form = screen.getByRole('form', { name: 'New column' })
    await user.click(within(form).getByRole('button', { name: 'Add column' }))
    expect(within(form).getByText('Enter a column name.')).toBeInTheDocument()

    await user.type(within(form).getByLabelText('Column name'), 'done')
    await user.click(within(form).getByRole('button', { name: 'Add column' }))
    expect(
      await within(form).findByText('A column named "done" already exists'),
    ).toBeInTheDocument()

    await user.clear(within(form).getByLabelText('Column name'))
    await user.type(within(form).getByLabelText('Column name'), 'Review')
    await user.click(within(form).getByLabelText('Marks tasks complete'))
    await user.click(within(form).getByRole('button', { name: 'Add column' }))

    const review = await column('Review')
    expect(within(review).getByText('Done')).toBeInTheDocument()
    expect(db.statuses.find((s) => s.name === 'Review')?.is_done).toBe(true)
  })

  it('renames a column inline', async () => {
    const { user } = renderApp('/board')

    await user.click(await screen.findByRole('button', { name: 'Rename column Doing' }))
    const input = screen.getByLabelText('Column name')
    await user.clear(input)
    await user.type(input, 'In progress{Enter}')

    expect(await column('In progress')).toBeInTheDocument()
  })

  it('cancels a rename with Escape and validates the name', async () => {
    const { user } = renderApp('/board')

    await user.click(await screen.findByRole('button', { name: 'Rename column Doing' }))
    await user.clear(screen.getByLabelText('Column name'))
    await user.keyboard('{Enter}')
    expect(screen.getByRole('alert')).toHaveTextContent('Enter a column name.')

    await user.keyboard('{Escape}')
    expect(screen.getByRole('button', { name: 'Rename column Doing' })).toBeInTheDocument()
  })

  it('moves a column right from its menu', async () => {
    const requests = recordRequests()
    const { user } = renderApp('/board')

    await user.click(await screen.findByRole('button', { name: 'To do column actions' }))
    await user.click(screen.getByRole('menuitem', { name: 'Move right' }))

    await waitFor(() => {
      expect(requests).toEqual([
        {
          method: 'POST',
          path: `/statuses/${ids.todo}/move`,
          body: { after_id: ids.doing, before_id: ids.done },
        },
      ])
    })
    await waitFor(() => {
      const board = screen.getByRole('region', { name: 'Board' })
      expect(
        within(board)
          .getAllByRole('region')
          .map((r) => r.getAttribute('aria-label')),
      ).toEqual(['Doing', 'To do', 'Done'])
    })
  })

  it("explains why a column that still has tasks can't be deleted", async () => {
    const { user } = renderApp('/board')

    await user.click(await screen.findByRole('button', { name: 'To do column actions' }))
    await user.click(screen.getByRole('menuitem', { name: 'Delete' }))
    const dialog = await screen.findByRole('alertdialog')
    await user.click(within(dialog).getByRole('button', { name: 'Delete column' }))

    expect(
      await within(dialog).findByText('Status still has tasks; move or delete them first'),
    ).toBeInTheDocument()
    expect(db.statuses).toHaveLength(3)
  })

  it('deletes an empty column', async () => {
    const { user } = renderApp('/board')

    await user.click(await screen.findByRole('button', { name: 'Doing column actions' }))
    await user.click(screen.getByRole('menuitem', { name: 'Delete' }))
    await user.click(
      within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Delete column' }),
    )

    await waitFor(() => {
      expect(screen.queryByRole('region', { name: 'Doing' })).not.toBeInTheDocument()
    })
    expect(toast.success).toHaveBeenCalledWith('Deleted the “Doing” column.')
  })

  it('invites you to add a column when the board is empty', async () => {
    db.statuses = []
    db.tasks = []
    renderApp('/board')

    expect(await screen.findByText('Your board has no columns yet.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add column' })).toBeInTheDocument()
  })
})
