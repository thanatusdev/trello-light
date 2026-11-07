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

beforeEach(() => {
  useAuthStore.getState().setTokens(tokens.initial)
})

async function openEdit(taskId: string) {
  const app = renderApp(`/board?task=${taskId}`)
  const dialog = await screen.findByRole('dialog', { name: 'Edit task' })
  await within(dialog).findByLabelText('Title')
  return { ...app, dialog }
}

describe('creating a task', () => {
  it('validates the form before sending anything', async () => {
    const requests = recordRequests()
    const { user } = renderApp('/board?task=new')
    const dialog = await screen.findByRole('dialog', { name: 'New task' })

    await user.click(await within(dialog).findByRole('button', { name: 'Create task' }))

    expect(await within(dialog).findByText('Enter a title.')).toBeInTheDocument()
    expect(requests).toEqual([])
  })

  it('creates the task in the chosen column and closes', async () => {
    const requests = recordRequests()
    const { user, router } = renderApp(`/board?task=new&status=${ids.doing}`)
    const dialog = await screen.findByRole('dialog', { name: 'New task' })

    await user.type(await within(dialog).findByLabelText('Title'), '  Review PR  ')
    await user.type(within(dialog).getByLabelText('Description'), 'Look at the diff')
    await user.click(within(dialog).getByRole('combobox', { name: 'Assignee' }))
    await user.click(await screen.findByRole('option', { name: 'Bob Jones' }))
    await user.click(within(dialog).getByRole('button', { name: 'Create task' }))

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
    expect(router.state.location.search).toBe('')
    expect(requests).toEqual([
      {
        method: 'POST',
        path: '/tasks',
        body: {
          title: 'Review PR',
          description: 'Look at the diff',
          status_id: ids.doing,
          assignee_id: ids.bob,
          due_date: null,
        },
      },
    ])
    expect(
      within(await screen.findByRole('region', { name: 'Doing' })).getByText('Review PR'),
    ).toBeInTheDocument()
  })

  it("shows the server's error and keeps the modal open", async () => {
    server.use(
      http.post(`${API}/tasks`, () =>
        HttpResponse.json({ detail: 'due_date cannot be in the past' }, { status: 422 }),
      ),
    )
    const { user } = renderApp('/board?task=new')
    const dialog = await screen.findByRole('dialog', { name: 'New task' })

    await user.type(await within(dialog).findByLabelText('Title'), 'Late')
    await user.click(within(dialog).getByRole('button', { name: 'Create task' }))

    expect(await within(dialog).findByText('due_date cannot be in the past')).toBeInTheDocument()
  })

  it('asks for a column first when the board has none', async () => {
    db.statuses = []
    db.tasks = []
    renderApp('/board?task=new')

    expect(await screen.findByText('Create a column before adding tasks.')).toBeInTheDocument()
  })
})

describe('editing a task', () => {
  it('sends only the fields that changed', async () => {
    const requests = recordRequests()
    const { user, dialog } = await openEdit(ids.readme)

    const title = within(dialog).getByLabelText('Title')
    await user.clear(title)
    await user.type(title, 'Write the docs')
    await user.click(within(dialog).getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
    expect(requests).toEqual([
      { method: 'PATCH', path: `/tasks/${ids.readme}`, body: { title: 'Write the docs' } },
    ])
  })

  it('changes the assignee and clears the due date through their own endpoints', async () => {
    const requests = recordRequests()
    const { user, dialog } = await openEdit(ids.readme)

    await user.click(within(dialog).getByRole('combobox', { name: 'Assignee' }))
    await user.click(await screen.findByRole('option', { name: 'Unassigned' }))
    await user.click(within(dialog).getByRole('button', { name: 'Clear due date' }))
    await user.click(within(dialog).getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(requests).toEqual([
        { method: 'PATCH', path: `/tasks/${ids.readme}`, body: { due_date: null } },
        { method: 'PUT', path: `/tasks/${ids.readme}/assignee`, body: { assignee_id: null } },
      ])
    })
  })

  it('marks a task complete by moving it to the first done column', async () => {
    const requests = recordRequests()
    const { user, dialog } = await openEdit(ids.schema)

    await user.click(within(dialog).getByRole('checkbox', { name: 'Mark complete' }))
    expect(within(dialog).getByText('Saving moves it to “Done”.')).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(requests).toEqual([
        { method: 'POST', path: `/tasks/${ids.schema}/move`, body: { status_id: ids.done } },
      ])
    })
    expect(db.tasks.find((t) => t.id === ids.schema)?.completed_at).not.toBeNull()
  })

  it('reopens a completed task by moving it to the first open column', async () => {
    const requests = recordRequests()
    const { user, dialog } = await openEdit(ids.ship)

    const box = within(dialog).getByRole('checkbox', { name: 'Mark complete' })
    expect(box).toBeChecked()
    await user.click(box)
    await user.click(within(dialog).getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(requests).toEqual([
        { method: 'POST', path: `/tasks/${ids.ship}/move`, body: { status_id: ids.todo } },
      ])
    })
  })

  it('disables "Mark complete" when there is no done column', async () => {
    db.statuses = db.statuses.filter((s) => !s.is_done)
    const { dialog } = await openEdit(ids.readme)

    const box = within(dialog).getByRole('checkbox', { name: 'Mark complete' })
    expect(box).toBeDisabled()
    // The reason is visible text tied to the checkbox, not a hover-only tooltip.
    expect(box).toHaveAccessibleDescription('Add a column that marks tasks complete first.')
    expect(within(dialog).getByText('Add a column that marks tasks complete first.')).toBeVisible()
  })

  it('deletes the task after confirmation', async () => {
    const { user, dialog } = await openEdit(ids.readme)

    await user.click(within(dialog).getByRole('button', { name: 'Delete' }))
    const confirm = await screen.findByRole('alertdialog', { name: 'Delete this task?' })
    await user.click(within(confirm).getByRole('button', { name: 'Delete task' }))

    await waitFor(() => {
      expect(screen.queryByText('Write the README')).not.toBeInTheDocument()
    })
    expect(db.tasks.some((t) => t.id === ids.readme)).toBe(false)
    expect(toast.success).toHaveBeenCalledWith('Task deleted.')
  })

  it('puts the task back and explains when the delete fails', async () => {
    server.use(
      http.delete(`${API}/tasks/:id`, () =>
        HttpResponse.json({ detail: 'Not allowed' }, { status: 403 }),
      ),
    )
    const { user, dialog } = await openEdit(ids.readme)

    await user.click(within(dialog).getByRole('button', { name: 'Delete' }))
    await user.click(
      within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Delete task' }),
    )

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Couldn't delete the task. Not allowed")
    })
    expect(await screen.findByText('Write the README')).toBeInTheDocument()
  })

  it('says so when the task no longer exists', async () => {
    renderApp('/board?task=7a5c0000-0000-4000-8000-000000000999')

    expect(await screen.findByText('This task no longer exists.')).toBeInTheDocument()
  })
})
