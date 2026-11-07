import { expect, test } from '../fixtures/test'

// Drags use dnd-kit's keyboard sensor (Space, arrows, Space on the card's "Move" grip): it is
// deterministic, needs no pixel geometry, and each step is confirmed by dnd-kit's live-region
// announcement. One test also drives the pointer sensor with stepped mouse moves, within a
// single column so both cards are on screen.
//
// Each test drags between columns it created itself: moves send the neighbours the client
// saw, so sharing seeded columns with parallel tests would (correctly) produce 409s.

test('moves a task to another column and keeps it after a reload', async ({ board, api, uid }) => {
  const from = await api.createColumn(`${uid} backlog`)
  const to = await api.createColumn(`${uid} doing`)
  const task = await api.createTask({ title: `${uid} ship it`, statusId: from.id })

  await board.goto()
  await board.keyboardMoveToColumn(task.title, to.name)
  await board.expectTaskIn(to.name, task.title)

  await board.page.reload()
  await board.expectLoaded()
  await board.expectTaskIn(to.name, task.title)
  await expect(
    board.column(from.name).getByRole('button', { name: `Open ${task.title}` }),
  ).toHaveCount(0)
})

test('marks a task completed when it is moved into a done column', async ({ board, api, uid }) => {
  const from = await api.createColumn(`${uid} review`)
  const done = await api.createColumn(`${uid} shipped`, true)
  const task = await api.createTask({ title: `${uid} finish`, statusId: from.id })

  await board.goto()
  const card = board.card(task.title)
  await expect(card.getByText('Done', { exact: true })).toHaveCount(0)
  await board.keyboardMoveToColumn(task.title, done.name)

  await board.expectTaskIn(done.name, task.title)
  await expect(card.getByText('Done', { exact: true })).toBeVisible()
  await expect(card.getByText(task.title, { exact: true })).toHaveCSS(
    'text-decoration-line',
    'line-through',
  )
  expect((await api.task(task.id)).completed_at).not.toBeNull()
})

test('reorders tasks within a column and keeps the order after a reload', async ({
  board,
  api,
  uid,
}) => {
  const column = await api.createColumn(`${uid} sprint`)
  for (const name of ['first', 'second', 'third']) {
    await api.createTask({ title: `${uid} ${name}`, statusId: column.id })
  }
  const order = (...names: string[]) => names.map((n) => `Open ${uid} ${n}`)

  await board.goto()
  await expect(board.cardsIn(column.name, uid)).toHaveText(order('first', 'second', 'third'))

  await board.keyboardReorder(`${uid} third`, 'ArrowUp', 2)
  await expect(board.cardsIn(column.name, uid)).toHaveText(order('first', 'third', 'second'))

  await board.page.reload()
  await board.expectLoaded()
  await expect(board.cardsIn(column.name, uid)).toHaveText(order('first', 'third', 'second'))
})

test('reorders a task with a mouse drag', async ({ board, api, uid }) => {
  // One column: both cards are on screen however many columns parallel tests have added.
  const column = await api.createColumn(`${uid} mouse`)
  for (const name of ['first', 'second', 'third']) {
    await api.createTask({ title: `${uid} ${name}`, statusId: column.id })
  }
  const order = (...names: string[]) => names.map((n) => `Open ${uid} ${n}`)

  await board.goto()
  await board.pointerDrag(`${uid} third`, `${uid} first`)
  await expect(board.cardsIn(column.name, uid)).toHaveText(order('third', 'first', 'second'))

  await board.page.reload()
  await board.expectLoaded()
  await expect(board.cardsIn(column.name, uid)).toHaveText(order('third', 'first', 'second'))
})
