import { devices } from '@playwright/test'

import { SEEDED } from '../fixtures/env'
import { expect, test } from '../fixtures/test'

// Pixel 7 emulation (touch, 412px wide); `defaultBrowserType` can't be set per file.
const { defaultBrowserType, ...pixel7 } = devices['Pixel 7']
test.use(pixel7)
// eslint-disable-next-line playwright/no-skipped-test -- conditional: other engines lack isMobile
test.skip(({ browserName }) => browserName !== 'chromium', 'isMobile emulation is Chromium-only')

test('the board scrolls horizontally without the page overflowing', async ({ page, board }) => {
  await board.goto()
  const first = board.column(SEEDED.todo)
  await expect(first).toBeInViewport()
  await expect(board.addColumn).not.toBeInViewport()

  // No sideways scroll on the page itself: only the board region scrolls.
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )

  // Scroll the board all the way right: the last item comes into view, the first leaves.
  await board.region.hover()
  await page.mouse.wheel(10_000, 0)
  await expect(board.addColumn).toBeInViewport()
  await expect(first).not.toBeInViewport()
})

test('the task modal is usable on a phone', async ({ board, taskModal, api, uid }) => {
  const todo = await api.column(SEEDED.todo)
  const task = await api.createTask({ title: `${uid} on the go`, statusId: todo.id })
  const renamed = `${uid} edited on a phone`

  await board.goto()
  await board.openButton(task.title).tap()
  await taskModal.expectOpen('Edit')

  // The whole dialog fits on the 412px-wide screen (no sideways overflow).
  await expect(taskModal.dialog).toBeInViewport({ ratio: 1 })

  await taskModal.title.fill(renamed)
  await taskModal.save.scrollIntoViewIfNeeded()
  await expect(taskModal.save).toBeInViewport()
  await taskModal.save.tap()

  await expect(taskModal.dialog).toBeHidden()
  await board.expectTaskIn(SEEDED.todo, renamed)
})
