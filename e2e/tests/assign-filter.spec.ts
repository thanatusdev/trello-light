import { env, SEEDED } from '../fixtures/env'
import { expect, test } from '../fixtures/test'

test('assigns a task to another user and filters by assignee', async ({
  page,
  board,
  taskModal,
  filterBar,
  api,
  uid,
}) => {
  const todo = await api.column(SEEDED.todo)
  const bob = await api.user(env.otherUserName)
  const forBob = await api.createTask({ title: `${uid} for bob`, statusId: todo.id })
  const unassigned = await api.createTask({ title: `${uid} nobody`, statusId: todo.id })

  await board.goto()
  await board.openTask(forBob.title)
  await taskModal.expectOpen('Edit')
  await taskModal.chooseAssignee(env.otherUserName)
  await taskModal.save.click()
  await expect(taskModal.dialog).toBeHidden()
  await expect(board.card(forBob.title)).toContainText(`Assigned to ${env.otherUserName}`)

  await filterBar.byAssignee(env.otherUserName)
  await expect(page).toHaveURL(new RegExp(`assignee_id=${bob.id}`))
  await expect(board.openButton(forBob.title)).toBeVisible()
  await expect(board.openButton(unassigned.title)).toHaveCount(0)
  expect((await api.task(forBob.id)).assignee?.id).toBe(bob.id)
})
