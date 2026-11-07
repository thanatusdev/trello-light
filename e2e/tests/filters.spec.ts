import { isoDaysFromToday } from '../fixtures/dates'
import { SEEDED } from '../fixtures/env'
import { expect, test } from '../fixtures/test'

test('filters by column and keeps the filter after a reload', async ({
  page,
  board,
  filterBar,
  api,
  uid,
}) => {
  const todo = await api.column(SEEDED.todo)
  const inProgress = await api.column(SEEDED.inProgress)
  const waiting = await api.createTask({ title: `${uid} waiting`, statusId: todo.id })
  const active = await api.createTask({ title: `${uid} active`, statusId: inProgress.id })

  await board.goto()
  await filterBar.byColumn(SEEDED.inProgress)

  await expect(page).toHaveURL(new RegExp(`status_id=${inProgress.id}`))
  await expect(board.column(SEEDED.todo)).toHaveCount(0)
  await expect(board.openButton(active.title)).toBeVisible()
  await expect(board.openButton(waiting.title)).toHaveCount(0)

  await page.reload()
  await board.expectLoaded()
  await expect(filterBar.column).toHaveText(SEEDED.inProgress)
  await expect(board.column(SEEDED.todo)).toHaveCount(0)
  await expect(board.openButton(active.title)).toBeVisible()
})

test('filters by due date range and keeps it after a reload', async ({
  page,
  board,
  filterBar,
  api,
  uid,
}) => {
  const todo = await api.column(SEEDED.todo)
  const [from, until] = [isoDaysFromToday(1), isoDaysFromToday(7)]
  const soon = await api.createTask({
    title: `${uid} soon`,
    statusId: todo.id,
    dueDate: isoDaysFromToday(3),
  })
  const later = await api.createTask({
    title: `${uid} later`,
    statusId: todo.id,
    dueDate: isoDaysFromToday(30),
  })
  const undated = await api.createTask({ title: `${uid} undated`, statusId: todo.id })

  await board.goto()
  await filterBar.byDueRange(from, until)

  await expect(page).toHaveURL(new RegExp(`due_after=${from}`))
  await expect(page).toHaveURL(new RegExp(`due_before=${until}`))
  const expectFiltered = async () => {
    await expect(board.openButton(soon.title)).toBeVisible()
    await expect(board.openButton(later.title)).toHaveCount(0)
    await expect(board.openButton(undated.title)).toHaveCount(0)
  }
  await expectFiltered()

  await page.reload()
  await board.expectLoaded()
  await expectFiltered()
  await expect(filterBar.clearButton()).toHaveText('Clear filters (2)')
})
