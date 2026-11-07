import { expect, type Locator, type Page, type Response } from '@playwright/test'

export class BoardPage {
  readonly region: Locator
  readonly signOut: Locator
  readonly addColumn: Locator

  constructor(readonly page: Page) {
    this.region = page.getByRole('region', { name: 'Board' })
    this.signOut = page.getByRole('button', { name: 'Sign out' })
    this.addColumn = this.region.getByRole('button', { name: 'Add column' })
  }

  async goto(query = ''): Promise<void> {
    await this.page.goto(`/board${query}`)
    await this.expectLoaded()
  }

  async expectLoaded(): Promise<void> {
    await expect(this.region).toBeVisible()
    await expect(this.page.getByRole('status', { name: 'Loading board' })).toBeHidden()
  }

  column(name: string): Locator {
    return this.region.getByRole('region', { name, exact: true })
  }

  /** The card's open button; its accessible name is "Open <title>". */
  openButton(title: string): Locator {
    return this.region.getByRole('button', { name: `Open ${title}`, exact: true })
  }

  card(title: string): Locator {
    // `has` is relative to each list item, so it must not be rooted at the board region.
    return this.region
      .getByRole('listitem')
      .filter({ has: this.page.getByRole('button', { name: `Open ${title}`, exact: true }) })
  }

  /** Open buttons of the cards in a column whose title contains `marker`, in board order. */
  cardsIn(column: string, marker: string): Locator {
    return this.column(column).getByRole('button', { name: new RegExp(`^Open .*${marker}`) })
  }

  async expectTaskIn(column: string, title: string): Promise<void> {
    await expect(this.column(column).getByRole('button', { name: `Open ${title}` })).toBeVisible()
  }

  async openTask(title: string): Promise<void> {
    await this.openButton(title).click()
  }

  async addTaskTo(column: string): Promise<void> {
    await this.column(column)
      .getByRole('button', { name: `Add task to ${column}` })
      .click()
  }

  /** dnd-kit's live region while `title` is being dragged ("task “…” moved to … in “Col”."). */
  dragAnnouncement(title: string): Locator {
    return this.page.getByRole('status').filter({ hasText: `task “${title}”` })
  }

  waitForMove(): Promise<Response> {
    return this.page.waitForResponse(
      (r) => /\/api\/v1\/tasks\/[^/]+\/move$/.test(r.url()) && r.request().method() === 'POST',
    )
  }

  /** Space on the card's "Move <title>" grip starts a keyboard drag. */
  private async pickUp(title: string): Promise<Locator> {
    await this.region.getByRole('button', { name: `Move ${title}`, exact: true }).focus()
    await this.page.keyboard.press('Space')
    const live = this.dragAnnouncement(title)
    // "Picked up …" is announced as the drag starts; dnd-kit then measures the board and
    // announces "… moved to …" (over itself) once it's initialised. Keys sent before that are
    // dropped, so wait for it.
    await expect(live).toContainText('moved to')
    // The sensor's keydown listener is attached in a setTimeout(0) queued at drag start;
    // yielding one task in the page guarantees it ran. An ordering barrier, not a timed wait.
    await this.page.evaluate(() => new Promise((resolve) => setTimeout(resolve, 0)))
    return live
  }

  /** Space drops the card; resolves once the move request succeeded, so a reload sees it. */
  private async drop(live: Locator): Promise<void> {
    const moved = this.waitForMove()
    await this.page.keyboard.press('Space')
    await expect(live).toContainText('dropped at')
    expect((await moved).ok()).toBe(true)
  }

  /**
   * Presses `key` until dnd-kit announces `target`, confirming each press before the next.
   * A press is not always a move: the sensor may spend one scrolling a container into view.
   */
  private async stepUntil(live: Locator, key: string, target: string): Promise<void> {
    for (let step = 0; step < 20; step++) {
      const before = (await live.textContent()) ?? ''
      if (before.includes(target)) break
      await this.page.keyboard.press(key)
      await expect(live).not.toHaveText(before)
    }
    await expect(live).toContainText(target)
  }

  /** Keyboard-drags a card into `column`; columns in between are stepped over. */
  async keyboardMoveToColumn(
    title: string,
    column: string,
    key: 'ArrowLeft' | 'ArrowRight' = 'ArrowRight',
  ): Promise<void> {
    const live = await this.pickUp(title)
    await this.stepUntil(live, key, `in “${column}”.`)
    await this.drop(live)
  }

  /** Keyboard-drags a card up or down its column to (1-based) `position`. */
  async keyboardReorder(
    title: string,
    key: 'ArrowUp' | 'ArrowDown',
    position: number,
  ): Promise<void> {
    const live = await this.pickUp(title)
    await this.stepUntil(live, key, `moved to position ${position} of`)
    await this.drop(live)
  }

  /**
   * Drags a card with the mouse onto another card. Moves in small steps so dnd-kit's pointer
   * sensor passes its 6px activation distance and sees intermediate drag-over events.
   */
  async pointerDrag(title: string, ontoTitle: string): Promise<void> {
    const card = this.card(title)
    const target = this.card(ontoTitle)
    await card.scrollIntoViewIfNeeded()
    await expect(card).toBeInViewport()
    await expect(target).toBeInViewport()
    const source = await card.boundingBox()
    const dest = await target.boundingBox()
    if (!source || !dest) throw new Error('Card or drop target is not on screen')
    const moved = this.waitForMove()
    await this.page.mouse.move(source.x + source.width / 2, source.y + source.height / 2)
    await this.page.mouse.down()
    await this.page.mouse.move(source.x + source.width / 2, source.y + source.height / 2 - 10, {
      steps: 5,
    })
    await this.page.mouse.move(dest.x + dest.width / 2, dest.y + dest.height / 4, { steps: 20 })
    await this.page.mouse.up()
    expect((await moved).ok()).toBe(true)
  }

  // --- columns ---------------------------------------------------------------------

  async createColumn(name: string): Promise<void> {
    await this.addColumn.click()
    const form = this.region.getByRole('form', { name: 'New column' })
    await form.getByLabel('Column name').fill(name)
    await form.getByRole('button', { name: 'Add column' }).click()
    await expect(this.column(name)).toBeVisible()
  }

  async renameColumn(from: string, to: string): Promise<void> {
    await this.column(from)
      .getByRole('button', { name: `Rename column ${from}`, exact: true })
      .click()
    const input = this.region.getByRole('textbox', { name: 'Column name' })
    await input.fill(to)
    await input.press('Enter')
    await expect(this.column(to)).toBeVisible()
  }

  /** Opens the delete confirmation for a column and confirms; returns the dialog. */
  async requestColumnDelete(name: string): Promise<Locator> {
    await this.column(name)
      .getByRole('button', { name: `${name} column actions` })
      .click()
    await this.page.getByRole('menuitem', { name: 'Delete' }).click()
    const dialog = this.page.getByRole('alertdialog', { name: `Delete the “${name}” column?` })
    await dialog.getByRole('button', { name: 'Delete column' }).click()
    return dialog
  }
}
