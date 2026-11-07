import { SEEDED } from '../fixtures/env'
import { expect, test } from '../fixtures/test'

test('creates a task in the chosen column', async ({ page, board, taskModal, api, uid }) => {
  const title = `${uid} write release notes`
  await board.goto()
  await page.getByRole('button', { name: 'New task' }).click()
  await taskModal.expectOpen('New')
  await taskModal.title.fill(title)
  await taskModal.description.fill('Summarise the changes since the last release.')
  await taskModal.chooseColumn(SEEDED.inProgress)
  await taskModal.create.click()

  await expect(taskModal.dialog).toBeHidden()
  await board.expectTaskIn(SEEDED.inProgress, title)
  await expect(
    board.column(SEEDED.todo).getByRole('button', { name: `Open ${title}` }),
  ).toHaveCount(0)
  const [saved] = await api.tasksMatching(uid)
  expect(saved?.status_id).toBe((await api.column(SEEDED.inProgress)).id)
})

test('edits a task', async ({ board, taskModal, api, uid }) => {
  const todo = await api.column(SEEDED.todo)
  const task = await api.createTask({ title: `${uid} draft`, statusId: todo.id })
  const renamed = `${uid} final`

  await board.goto()
  await board.openTask(task.title)
  await taskModal.expectOpen('Edit')
  await expect(taskModal.title).toHaveValue(task.title)
  await taskModal.title.fill(renamed)
  await taskModal.description.fill('Now with details.')
  await taskModal.save.click()

  await expect(taskModal.dialog).toBeHidden()
  await board.expectTaskIn(SEEDED.todo, renamed)
  await expect(board.openButton(task.title)).toHaveCount(0)

  await board.openTask(renamed)
  await expect(taskModal.description).toHaveValue('Now with details.')
})

test('deletes a task after confirmation', async ({ board, taskModal, api, uid }) => {
  const todo = await api.column(SEEDED.todo)
  const task = await api.createTask({ title: `${uid} obsolete`, statusId: todo.id })

  await board.goto()
  await board.openTask(task.title)
  await taskModal.expectOpen('Edit')

  // Cancelling the confirmation keeps the task.
  await taskModal.delete.click()
  await taskModal.confirmDialog.getByRole('button', { name: 'Cancel' }).click()
  await expect(taskModal.confirmDialog).toBeHidden()
  await expect(taskModal.dialog).toBeVisible()

  await taskModal.deleteTask()
  await expect(board.page.getByText('Task deleted.')).toBeVisible()
  await expect(board.openButton(task.title)).toHaveCount(0)
  await board.page.reload()
  await board.expectLoaded()
  await expect(board.openButton(task.title)).toHaveCount(0)
})
