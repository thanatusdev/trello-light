import { expect, type Locator, type Page } from '@playwright/test'

export interface Registration {
  fullName: string
  email: string
  password: string
  confirmPassword?: string
}

export class RegisterPage {
  readonly heading: Locator
  readonly fullName: Locator
  readonly email: Locator
  readonly password: Locator
  readonly confirmPassword: Locator
  readonly submit: Locator
  readonly signInLink: Locator

  constructor(readonly page: Page) {
    this.heading = page.getByRole('heading', { name: 'Create an account' })
    this.fullName = page.getByLabel('Full name')
    this.email = page.getByLabel('Email')
    // Exact, or it would also match "Confirm password".
    this.password = page.getByLabel('Password', { exact: true })
    this.confirmPassword = page.getByLabel('Confirm password')
    this.submit = page.getByRole('button', { name: 'Create account' })
    this.signInLink = page.getByRole('link', { name: 'Sign in' })
  }

  async goto(): Promise<void> {
    await this.page.goto('/register')
    await expect(this.heading).toBeVisible()
  }

  async register({ fullName, email, password, confirmPassword }: Registration): Promise<void> {
    await this.fullName.fill(fullName)
    await this.email.fill(email)
    await this.password.fill(password)
    await this.confirmPassword.fill(confirmPassword ?? password)
    await this.submit.click()
  }

  /** A form-level or field-level message (both are announced as alerts). */
  message(text: string): Locator {
    return this.page.getByRole('alert').filter({ hasText: text })
  }
}
