import { screen, waitFor } from '@testing-library/react'
import { useState } from 'react'

import { db, ids } from '@/test/db'
import { renderWithQuery } from '@/test/query'
import { recordRequests } from '@/test/requests'

import { ColumnTitle } from './ColumnTitle'

function Harness({ name = 'Doing' }: { name?: string }) {
  const [editing, setEditing] = useState(false)
  return <ColumnTitle id={ids.doing} name={name} editing={editing} onEditingChange={setEditing} />
}

describe('ColumnTitle', () => {
  it('shows the name in a heading, with a descriptive rename button', () => {
    renderWithQuery(<Harness />)

    const button = screen.getByRole('button', { name: 'Rename column Doing' })
    expect(button).toHaveTextContent('Doing')
    expect(screen.getByRole('heading', { level: 2 })).toContainElement(button)
  })

  it('renames on Enter', async () => {
    const requests = recordRequests()
    const { user } = renderWithQuery(<Harness />)

    await user.click(screen.getByRole('button', { name: 'Rename column Doing' }))
    const input = screen.getByRole('textbox', { name: 'Column name' })
    expect(input).toHaveFocus()
    await user.clear(input)
    await user.type(input, ' In progress {Enter}')

    await waitFor(() => {
      expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    })
    expect(requests).toEqual([
      { method: 'PATCH', path: `/statuses/${ids.doing}`, body: { name: 'In progress' } },
    ])
    expect(db.statuses.find((s) => s.id === ids.doing)?.name).toBe('In progress')
  })

  it('saves on blur but sends nothing when the name is unchanged', async () => {
    const requests = recordRequests()
    const { user } = renderWithQuery(<Harness />)

    await user.click(screen.getByRole('button', { name: 'Rename column Doing' }))
    await user.tab()

    expect(screen.getByRole('button', { name: 'Rename column Doing' })).toBeInTheDocument()
    expect(requests).toEqual([])
  })

  it('validates, then cancels with Escape', async () => {
    const requests = recordRequests()
    const { user } = renderWithQuery(<Harness />)

    await user.click(screen.getByRole('button', { name: 'Rename column Doing' }))
    const input = screen.getByRole('textbox', { name: 'Column name' })
    await user.clear(input)
    await user.keyboard('{Enter}')

    expect(screen.getByRole('alert')).toHaveTextContent('Enter a column name.')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input).toHaveAccessibleDescription('Enter a column name.')

    await user.keyboard('{Escape}')
    expect(screen.getByRole('button', { name: 'Rename column Doing' })).toBeInTheDocument()
    expect(requests).toEqual([])
  })

  it('keeps the field open with the server refusal', async () => {
    const { user } = renderWithQuery(<Harness />)

    await user.click(screen.getByRole('button', { name: 'Rename column Doing' }))
    const input = screen.getByRole('textbox', { name: 'Column name' })
    await user.clear(input)
    await user.type(input, 'done{Enter}')

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'A column named "done" already exists',
    )
    expect(input).toBeInTheDocument()
  })
})
