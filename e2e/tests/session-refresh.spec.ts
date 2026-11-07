import { expect, test } from '../fixtures/test'

function expiryOf(jwt: string): number {
  const payload = jwt.split('.')[1] ?? ''
  return (JSON.parse(Buffer.from(payload, 'base64url').toString()) as { exp: number }).exp * 1000
}

test('keeps the session when the access token expires', async ({
  page,
  board,
  taskModal,
  api,
  uid,
}) => {
  // Loading the board exchanges the stored refresh token for a short-lived access token.
  const firstRefresh = page.waitForResponse((r) => r.url().endsWith('/api/v1/auth/refresh'))
  await board.goto()
  const { access_token } = (await (await firstRefresh).json()) as { access_token: string }
  const expiresAt = expiryOf(access_token)
  expect(expiresAt - Date.now()).toBeLessThan(60_000) // the e2e stack's short TTL is in effect

  // Whichever request goes out first with the stale token (board refetch, columns, or the
  // create itself) gets a 401; the app must refresh and carry on without bouncing to login.
  const seen: string[] = []
  page.on('response', (r) => {
    if (!r.url().includes('/api/v1/')) return
    if (r.status() === 401) seen.push('401')
    if (r.url().endsWith('/auth/refresh') && r.ok()) seen.push('refresh')
  })
  // Wait (by polling the clock, not sleeping) until the token the page holds has expired.
  await expect.poll(() => Date.now(), { timeout: 30_000 }).toBeGreaterThan(expiresAt + 1000)

  const title = `${uid} after expiry`
  await board.addTaskTo('To Do')
  await taskModal.title.fill(title)
  await taskModal.create.click()

  await expect(taskModal.dialog).toBeHidden()
  await board.expectTaskIn('To Do', title)
  await expect(page).toHaveURL(/\/board/)
  expect(await api.tasksMatching(uid)).toHaveLength(1)
  expect(seen.indexOf('401')).toBeGreaterThanOrEqual(0)
  expect(seen.indexOf('refresh', seen.indexOf('401'))).toBeGreaterThan(seen.indexOf('401'))
})
