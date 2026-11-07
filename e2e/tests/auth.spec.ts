import { env } from '../fixtures/env'
import { expect, test } from '../fixtures/test'

test.describe('signed out', () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test('signs in with valid credentials', async ({ page, loginPage, board }) => {
    await loginPage.goto()
    await loginPage.login(env.email, env.password)

    await expect(page).toHaveURL(/\/board$/)
    await board.expectLoaded()
    await expect(page.getByRole('banner').getByText(env.userName, { exact: true })).toBeVisible()
  })

  test('shows an error for a wrong password', async ({ page, loginPage, allowConsole }) => {
    allowConsole(/status of 401/)
    await loginPage.goto()
    await loginPage.login(env.email, 'not-the-password')

    await expect(loginPage.error).toHaveText('Incorrect email or password.')
    await expect(page).toHaveURL(/\/login$/)
  })

  test('redirects a protected route to login, then back after signing in', async ({
    page,
    loginPage,
  }) => {
    await page.goto('/tasks')

    await expect(page).toHaveURL(/\/login$/)
    await expect(loginPage.heading).toBeVisible()

    await loginPage.login(env.email, env.password)
    await expect(page).toHaveURL(/\/tasks$/)
  })
})

test('signs out and stays signed out after a reload', async ({ page, board, loginPage }) => {
  await board.goto()
  await board.signOut.click()

  await expect(loginPage.heading).toBeVisible()
  await page.reload()
  await expect(loginPage.heading).toBeVisible()
  await page.goto('/board')
  await expect(page).toHaveURL(/\/login$/)
})
