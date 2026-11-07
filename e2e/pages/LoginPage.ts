import { expect, type Locator, type Page } from '@playwright/test'

export class LoginPage {
  readonly heading: Locator
  readonly email: Locator
  readonly password: Locator
  readonly submit: Locator
  /** Server-side failure (wrong credentials, rate limited, ...). */
  readonly error: Locator

  constructor(readonly page: Page) {
    this.heading = page.getByRole('heading', { name: 'Sign in' })
    this.email = page.getByLabel('Email')
    this.password = page.getByLabel('Password')
    this.submit = page.getByRole('button', { name: 'Sign in' })
    this.error = page.getByRole('alert')
  }

  async goto(): Promise<void> {
    await this.page.goto('/login')
    await expect(this.heading).toBeVisible()
  }

  async login(email: string, password: string): Promise<void> {
    await this.email.fill(email)
    await this.password.fill(password)
    await this.submit.click()
  }
}
