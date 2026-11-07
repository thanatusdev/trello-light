import { env } from '../fixtures/env'
import { expect, test } from '../fixtures/test'
import { RegisterPage } from '../pages/RegisterPage'

// Signing up only makes sense signed out. Accounts can't be deleted through the API, so each
// test registers a throwaway address carrying its uid.
test.describe('sign up', () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test('creates an account, signs in and opens the board', async ({ page, board, uid }) => {
    const signUp = new RegisterPage(page)
    const fullName = `Newcomer ${uid}`
    await signUp.goto()

    await signUp.register({ fullName, email: `${uid}@example.com`, password: 'Sign-up-1234' })

    await expect(page).toHaveURL(/\/board$/)
    await board.expectLoaded()
    await expect(page.getByRole('banner').getByText(fullName, { exact: true })).toBeVisible()
  })

  test('refuses an email that is already registered', async ({ page, allowConsole }) => {
    allowConsole(/status of 409/)
    const signUp = new RegisterPage(page)
    await signUp.goto()

    await signUp.register({ fullName: 'Duplicate', email: env.email, password: 'Sign-up-1234' })

    await expect(signUp.message('An account with this email already exists.')).toBeVisible()
    await expect(page).toHaveURL(/\/register$/)
  })

  test('checks the passwords match before sending anything', async ({ page, uid }) => {
    const signUp = new RegisterPage(page)
    await signUp.goto()

    await signUp.register({
      fullName: 'Mismatch',
      email: `${uid}@example.com`,
      password: 'Sign-up-1234',
      confirmPassword: 'Sign-up-5678',
    })

    await expect(signUp.message("Passwords don't match.")).toBeVisible()
    await expect(signUp.confirmPassword).toHaveAttribute('aria-invalid', 'true')
  })

  test('links between sign in and sign up', async ({ page, loginPage }) => {
    const signUp = new RegisterPage(page)
    await loginPage.goto()

    await page.getByRole('link', { name: 'Create an account' }).click()
    await expect(signUp.heading).toBeVisible()

    await signUp.signInLink.click()
    await expect(loginPage.heading).toBeVisible()
  })
})
