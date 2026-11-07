import { expect, type Locator, type Page } from '@playwright/test'

import { dayButtonLabel, monthsFromNow } from '../fixtures/dates'

/** Picks `iso` in a react-day-picker popover opened by `trigger` (calendar starts on this month). */
export async function pickDate(page: Page, trigger: Locator, iso: string): Promise<void> {
  await trigger.click()
  const calendar = page.getByRole('dialog').filter({ has: page.getByRole('grid') })
  for (let i = 0; i < monthsFromNow(iso); i++) {
    await calendar.getByRole('button', { name: 'Go to the Next Month' }).click()
  }
  await calendar.getByRole('button', { name: dayButtonLabel(iso) }).click()
  await expect(calendar).toBeHidden()
}

/** Picks an option in a cmdk combobox (assignee pickers). */
export async function pickPerson(page: Page, trigger: Locator, name: string): Promise<void> {
  await trigger.click()
  await page.getByPlaceholder('Search people…').fill(name)
  await page.getByRole('option', { name, exact: true }).click()
  await expect(trigger).toHaveText(name)
}

export class TaskModal {
  readonly dialog: Locator
  readonly title: Locator
  readonly description: Locator
  readonly column: Locator
  readonly assignee: Locator
  readonly dueDate: Locator
  readonly create: Locator
  readonly save: Locator
  readonly cancel: Locator
  readonly delete: Locator
  readonly confirmDialog: Locator

  constructor(readonly page: Page) {
    this.dialog = page.getByRole('dialog', { name: /^(New|Edit) task$/ })
    this.title = this.dialog.getByLabel('Title')
    this.description = this.dialog.getByLabel('Description')
    this.column = this.dialog.getByRole('combobox', { name: 'Column' })
    this.assignee = this.dialog.getByRole('combobox', { name: 'Assignee' })
    this.dueDate = this.dialog.getByRole('button', { name: 'due date', exact: true })
    this.create = this.dialog.getByRole('button', { name: 'Create task' })
    this.save = this.dialog.getByRole('button', { name: 'Save' })
    this.cancel = this.dialog.getByRole('button', { name: 'Cancel' })
    this.delete = this.dialog.getByRole('button', { name: 'Delete', exact: true })
    this.confirmDialog = page.getByRole('alertdialog', { name: 'Delete this task?' })
  }

  /** Inline validation message under a field. */
  fieldError(message: string): Locator {
    return this.dialog.getByRole('alert').filter({ hasText: message })
  }

  async expectOpen(mode: 'New' | 'Edit'): Promise<void> {
    await expect(this.page.getByRole('dialog', { name: `${mode} task` })).toBeVisible()
    // Edit mode loads the task first; the form is ready once the title field shows.
    await expect(this.title).toBeVisible()
  }

  async chooseColumn(name: string): Promise<void> {
    await this.column.click()
    await this.page.getByRole('option', { name, exact: true }).click()
    await expect(this.column).toHaveText(name)
  }

  async chooseAssignee(name: string): Promise<void> {
    await pickPerson(this.page, this.assignee, name)
  }

  async chooseDueDate(iso: string): Promise<void> {
    await pickDate(this.page, this.dueDate, iso)
  }

  async deleteTask(): Promise<void> {
    await this.delete.click()
    await expect(this.confirmDialog).toBeVisible()
    await this.confirmDialog.getByRole('button', { name: 'Delete task' }).click()
    await expect(this.dialog).toBeHidden()
  }
}
