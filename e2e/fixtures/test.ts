import { randomBytes } from 'node:crypto'

import { test as base, type ConsoleMessage } from '@playwright/test'

import { BoardPage } from '../pages/BoardPage'
import { FilterBar } from '../pages/FilterBar'
import { LoginPage } from '../pages/LoginPage'
import { TaskModal } from '../pages/TaskModal'
import { Api, storedRefreshToken } from './api'
import { env } from './env'

/**
 * The e2e stack issues 5-second access tokens, so any test can hit a real 401 that the app
 * answers with a refresh and a retry. Chromium and WebKit log every 4xx response as a console
 * error; this is the one we tolerate globally: a 401 from an authenticated API call (not login
 * or refresh themselves) that is followed by a successful refresh.
 */
const EXPIRED_TOKEN_401 = 'Failed to load resource: the server responded with a status of 401'
const REFRESHABLE_URL = /\/api\/v1\/(?!auth\/(login|refresh)\b)/

interface Logged {
  at: number
  text: string
  url: string
}

interface Fixtures {
  /** Unique marker for names created by this test; cleaned up afterwards. */
  uid: string
  /** Allows console errors/warnings matching these patterns for this test only. */
  allowConsole: (...patterns: RegExp[]) => void
  consoleGuard: undefined
  api: Api
  loginPage: LoginPage
  board: BoardPage
  taskModal: TaskModal
  filterBar: FilterBar
}

const allowed = new WeakMap<object, RegExp[]>()

export const test = base.extend<Fixtures>({
  uid: async ({}, use) => {
    await use(`e2e-${randomBytes(4).toString('hex')}`)
  },

  allowConsole: async ({ page }, use) => {
    allowed.set(page, [])
    await use((...patterns) => {
      allowed.get(page)?.push(...patterns)
    })
  },

  consoleGuard: [
    async ({ page }, use, testInfo) => {
      const problems: Logged[] = []
      const tokenRetries: Logged[] = []
      const refreshes: number[] = []

      page.on('console', (message: ConsoleMessage) => {
        if (message.type() !== 'error' && message.type() !== 'warning') return
        const entry = { at: Date.now(), text: message.text(), url: message.location().url }
        if (entry.text.includes(EXPIRED_TOKEN_401) && REFRESHABLE_URL.test(entry.url)) {
          tokenRetries.push(entry)
        } else {
          problems.push(entry)
        }
      })
      page.on('pageerror', (error) => {
        problems.push({ at: Date.now(), text: `Uncaught ${error.name}: ${error.message}`, url: '' })
      })
      page.on('response', (response) => {
        if (response.url().endsWith('/api/v1/auth/refresh') && response.ok()) {
          refreshes.push(Date.now())
        }
      })

      await use(undefined)

      // A token 401 is only benign if the app recovered with a refresh after it.
      for (const retry of tokenRetries) {
        if (!refreshes.some((at) => at >= retry.at - 1000)) problems.push(retry)
      }
      const patterns = allowed.get(page) ?? []
      const unexpected = problems.filter((p) => !patterns.some((re) => re.test(p.text)))

      testInfo.annotations.push({
        type: 'token-refresh',
        description: `${tokenRetries.length} expired-token 401(s), ${refreshes.length} refresh(es)`,
      })
      if (unexpected.length > 0) {
        throw new Error(
          'Browser console errors/warnings:\n' +
            unexpected.map((p) => `  - ${p.text}${p.url ? ` (${p.url})` : ''}`).join('\n'),
        )
      }
    },
    { auto: true },
  ],

  api: async ({ playwright, uid }, use) => {
    const request = await playwright.request.newContext({ baseURL: env.baseURL })
    const api = new Api(request, await storedRefreshToken())
    await use(api)
    await api.cleanUp(uid).catch(() => undefined)
    await request.dispose()
  },

  loginPage: async ({ page }, use) => {
    await use(new LoginPage(page))
  },
  board: async ({ page }, use) => {
    await use(new BoardPage(page))
  },
  taskModal: async ({ page }, use) => {
    await use(new TaskModal(page))
  },
  filterBar: async ({ page }, use) => {
    await use(new FilterBar(page))
  },
})

export { expect } from '@playwright/test'
