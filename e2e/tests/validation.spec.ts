import { SEEDED } from '../fixtures/env'
import { expect, test } from '../fixtures/test'

test('shows validation messages for an empty or too long title', async ({
  board,
  taskModal,
  api,
  uid,
}) => {
  await board.goto()
  await board.addTaskTo(SEEDED.todo)
  await taskModal.expectOpen('New')

  await taskModal.create.click()
  await expect(taskModal.fieldError('Enter a title.')).toBeVisible()
  await expect(taskModal.title).toHaveAttribute('aria-invalid', 'true')

  await taskModal.title.fill(`${uid} ${'x'.repeat(200)}`)
  await taskModal.create.click()
  await expect(taskModal.fieldError('Title must be 200 characters or fewer.')).toBeVisible()

  // Nothing was saved, and fixing the title clears the error.
  await taskModal.title.fill(`${uid} short enough`)
  await expect(taskModal.fieldError('Title must be 200 characters or fewer.')).toBeHidden()
  await taskModal.cancel.click()
  await expect(taskModal.dialog).toBeHidden()
  expect(await api.tasksMatching(uid)).toHaveLength(0)
})
