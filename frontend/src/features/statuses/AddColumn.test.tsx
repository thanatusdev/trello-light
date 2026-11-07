import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'

import { db } from '@/test/db'
import { API } from '@/test/handlers'
import { renderWithQuery } from '@/test/query'
import { recordRequests } from '@/test/requests'
import { server } from '@/test/server'

import { AddColumn } from './AddColumn'

async function openForm() {
  const view = renderWithQuery(<AddColumn />)
  await view.user.click(screen.getByRole('button', { name: 'Add column' }))
  const form = screen.getByRole('form', { name: 'New column' })
  return { ...view, form, input: screen.getByLabelText('Column name') }
}

describe('AddColumn', () => {
  it('opens a form focused on the name', async () => {
    const { input } = await openForm()

    expect(input).toHaveFocus()
    expect(input).not.toHaveAttribute('aria-invalid')
    expect(input).not.toHaveAttribute('aria-describedby')
  })

  it('validates the name and links the error to the field', async () => {
    const requests = recordRequests()
    const { user, input } = await openForm()

    await user.click(screen.getByRole('button', { name: 'Add column' }))

    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input).toHaveAccessibleDescription('Enter a column name.')
    expect(requests).toEqual([])
  })

  it('creates a column and closes the form', async () => {
    const requests = recordRequests()
    const { user, input } = await openForm()

    await user.type(input, '  Review ')
    await user.click(screen.getByRole('checkbox', { name: 'Marks tasks complete' }))
    await user.click(screen.getByRole('button', { name: 'Add column' }))

    await waitFor(() => {
      expect(screen.queryByRole('form', { name: 'New column' })).not.toBeInTheDocument()
    })
    expect(requests).toEqual([
      { method: 'POST', path: '/statuses', body: { name: 'Review', is_done: true } },
    ])
    expect(db.statuses.at(-1)).toMatchObject({ name: 'Review', is_done: true })
  })

  it('shows a refusal from the server on the field', async () => {
    const { user, input } = await openForm()

    await user.type(input, 'doing')
    await user.click(screen.getByRole('button', { name: 'Add column' }))

    expect(await screen.findByText('A column named "doing" already exists')).toBeInTheDocument()
    expect(input).toHaveAccessibleDescription('A column named "doing" already exists')
    expect(screen.getByRole('form', { name: 'New column' })).toBeInTheDocument()
  })

  it('explains rate limiting', async () => {
    server.use(
      http.post(`${API}/statuses`, () =>
        HttpResponse.json({ detail: 'slow' }, { status: 429, headers: { 'Retry-After': '3' } }),
      ),
    )
    const { user, input } = await openForm()

    await user.type(input, 'Review')
    await user.click(screen.getByRole('button', { name: 'Add column' }))

    expect(
      await screen.findByText('Too many requests. Try again in 3 seconds.'),
    ).toBeInTheDocument()
  })

  it.each([
    [
      'Escape',
      async (user: ReturnType<typeof renderWithQuery>['user']) => user.keyboard('{Escape}'),
    ],
    [
      'Cancel',
      async (user: ReturnType<typeof renderWithQuery>['user']) =>
        user.click(screen.getByRole('button', { name: 'Cancel' })),
    ],
  ])('closes and resets on %s', async (_how, dismiss) => {
    const { user, input } = await openForm()
    await user.type(input, 'Half typed')

    await dismiss(user)

    expect(screen.queryByRole('form', { name: 'New column' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Add column' }))
    expect(screen.getByLabelText('Column name')).toHaveValue('')
  })
})
