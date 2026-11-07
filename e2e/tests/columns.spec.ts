import { expect, test } from '../fixtures/test'

test('creates, renames and deletes a column', async ({ page, board, api, uid }) => {
  const name = `${uid} Review`
  const renamed = `${uid} QA`

  await board.goto()
  await board.createColumn(name)
  await expect(board.column(name).getByText('No tasks yet')).toBeVisible()

  await board.renameColumn(name, renamed)
  await expect(board.column(name)).toHaveCount(0)
  await page.reload()
  await board.expectLoaded()
  await expect(board.column(renamed)).toBeVisible()
  expect((await api.columns()).map((c) => c.name)).toContain(renamed)

  const dialog = await board.requestColumnDelete(renamed)
  await expect(dialog).toBeHidden()
  await expect(page.getByText(`Deleted the “${renamed}” column.`)).toBeVisible()
  await expect(board.column(renamed)).toHaveCount(0)
  expect((await api.columns()).map((c) => c.name)).not.toContain(renamed)
})

test('refuses to delete a column that still has tasks', async ({
  board,
  api,
  uid,
  allowConsole,
}) => {
  allowConsole(/status of 409/)
  const column = await api.createColumn(`${uid} Blocked`)
  await api.createTask({ title: `${uid} stuck`, statusId: column.id })

  await board.goto()
  const dialog = await board.requestColumnDelete(column.name)

  await expect(dialog.getByRole('alert')).toHaveText(
    'Status still has tasks; move or delete them first',
  )
  await dialog.getByRole('button', { name: 'Cancel' }).click()
  await expect(dialog).toBeHidden()
  await expect(board.column(column.name)).toBeVisible()
  await board.expectTaskIn(column.name, `${uid} stuck`)
})
