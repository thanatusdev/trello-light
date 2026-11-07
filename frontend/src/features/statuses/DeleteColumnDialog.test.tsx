import { screen, waitFor } from '@testing-library/react'
import { toast } from 'sonner'

import { db, ids } from '@/test/db'
import { renderWithQuery } from '@/test/query'

import { DeleteColumnDialog } from './DeleteColumnDialog'

vi.mock('sonner', async (importOriginal) => {
  const actual = await importOriginal<typeof import('sonner')>()
  return { ...actual, toast: { error: vi.fn(), success: vi.fn() } }
})

function renderDialog(id: string, name: string) {
  const onOpenChange = vi.fn()
  const view = renderWithQuery(
    <DeleteColumnDialog id={id} name={name} open onOpenChange={onOpenChange} />,
  )
  return { ...view, onOpenChange, dialog: screen.getByRole('alertdialog') }
}

describe('DeleteColumnDialog', () => {
  it('asks for confirmation and explains the rule', () => {
    renderDialog(ids.doing, 'Doing')

    expect(
      screen.getByRole('alertdialog', { name: 'Delete the “Doing” column?' }),
    ).toHaveAccessibleDescription(
      'Only empty columns can be deleted. Tasks are never deleted with a column.',
    )
  })

  it('deletes an empty column, closes and confirms', async () => {
    const { user, onOpenChange } = renderDialog(ids.doing, 'Doing')

    await user.click(screen.getByRole('button', { name: 'Delete column' }))

    await waitFor(() => {
      expect(onOpenChange).toHaveBeenCalledWith(false)
    })
    expect(toast.success).toHaveBeenCalledWith('Deleted the “Doing” column.')
    expect(db.statuses.some((s) => s.id === ids.doing)).toBe(false)
  })

  it('stays open and says why when the column still has tasks (409)', async () => {
    const { user, onOpenChange } = renderDialog(ids.todo, 'To do')

    await user.click(screen.getByRole('button', { name: 'Delete column' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Status still has tasks; move or delete them first',
    )
    expect(onOpenChange).not.toHaveBeenCalled()
    expect(db.statuses.some((s) => s.id === ids.todo)).toBe(true)
    expect(screen.getByRole('button', { name: 'Delete column' })).toBeEnabled()
  })

  it('clears the refusal when cancelled', async () => {
    const { user, onOpenChange } = renderDialog(ids.todo, 'To do')
    await user.click(screen.getByRole('button', { name: 'Delete column' }))
    await screen.findByRole('alert')

    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(onOpenChange).toHaveBeenCalledWith(false)
  })
})
