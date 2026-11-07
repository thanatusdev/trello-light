import { expect, type Locator, type Page } from '@playwright/test'

import { pickDate, pickPerson } from './TaskModal'

export class FilterBar {
  readonly root: Locator
  readonly search: Locator
  readonly column: Locator
  readonly assignee: Locator
  readonly progress: Locator
  readonly dueFrom: Locator
  readonly dueUntil: Locator

  constructor(readonly page: Page) {
    this.root = page.getByRole('search', { name: 'Filter tasks' })
    this.search = this.root.getByLabel('Search')
    this.column = this.root.getByRole('combobox', { name: 'Column' })
    this.assignee = this.root.getByRole('combobox', { name: 'Assignee' })
    this.progress = this.root.getByRole('combobox', { name: 'Progress' })
    this.dueFrom = this.root.getByRole('button', { name: 'due from', exact: true })
    this.dueUntil = this.root.getByRole('button', { name: 'due until', exact: true })
  }

  clearButton(): Locator {
    return this.root.getByRole('button', { name: /^Clear filters/ })
  }

  async byColumn(name: string): Promise<void> {
    await this.column.click()
    await this.page.getByRole('option', { name, exact: true }).click()
    await expect(this.column).toHaveText(name)
  }

  async byAssignee(name: string): Promise<void> {
    await pickPerson(this.page, this.assignee, name)
  }

  async byDueRange(from: string, until: string): Promise<void> {
    await pickDate(this.page, this.dueFrom, from)
    await pickDate(this.page, this.dueUntil, until)
  }
}
