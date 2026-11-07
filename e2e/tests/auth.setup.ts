import { STORAGE_STATE, env } from '../fixtures/env'
import { expect, test as setup } from '../fixtures/test'

setup('sign in once and save the session', async ({ page, loginPage, board }) => {
  await loginPage.goto()
  await loginPage.login(env.email, env.password)
  await board.expectLoaded()
  await expect(page.getByRole('banner').getByText(env.userName, { exact: true })).toBeVisible()
  await page.context().storageState({ path: STORAGE_STATE })
})
