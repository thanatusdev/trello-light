import { defineConfig, devices } from '@playwright/test'

import { env, STORAGE_STATE } from './fixtures/env'

const allBrowsers = process.env.E2E_ALL_BROWSERS === '1'
const signedIn = { storageState: STORAGE_STATE }

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: env.baseURL,
    // Matches the app's notion of "today" (UTC) so date pickers are deterministic.
    timezoneId: 'UTC',
    locale: 'en-US',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    { name: 'setup', testMatch: /.*\.setup\.ts/ },
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'], ...signedIn },
      dependencies: ['setup'],
    },
    ...(allBrowsers
      ? [
          {
            name: 'firefox',
            use: { ...devices['Desktop Firefox'], ...signedIn },
            dependencies: ['setup'],
          },
          {
            name: 'webkit',
            use: { ...devices['Desktop Safari'], ...signedIn },
            dependencies: ['setup'],
          },
        ]
      : []),
  ],
})
