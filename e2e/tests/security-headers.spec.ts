import type { APIResponse } from '@playwright/test'

import { expect, test } from '../fixtures/test'

const SECURITY_HEADERS = {
  'x-frame-options': 'DENY',
  'x-content-type-options': 'nosniff',
  'referrer-policy': 'strict-origin-when-cross-origin',
} as const

function expectSecurityHeaders(response: APIResponse): void {
  const headers = response.headers()
  for (const [name, value] of Object.entries(SECURITY_HEADERS)) {
    expect(headers[name], name).toBe(value)
  }
  // nginx should not advertise its version.
  expect(headers.server ?? '').not.toMatch(/\d/)
}

// nginx drops server-level add_header directives in any location that sets its own, so every
// kind of response the web container serves is checked, not just one.
test.describe('security headers', () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test('are sent with the SPA entry point', async ({ request }) => {
    const response = await request.get('/')

    expect(response.ok()).toBe(true)
    expect(response.headers()['cache-control']).toBe('no-cache')
    expectSecurityHeaders(response)
  })

  test('are sent with a client-side route served by the SPA fallback', async ({ request }) => {
    const response = await request.get('/board')

    expect(response.ok()).toBe(true)
    expectSecurityHeaders(response)
  })

  test('are sent with hashed build assets', async ({ request }) => {
    const html = await (await request.get('/')).text()
    const asset = /(?:src|href)="(\/assets\/[^"]+)"/.exec(html)?.[1]
    if (!asset) throw new Error('index.html does not reference a built asset')

    const response = await request.get(asset)

    expect(response.ok()).toBe(true)
    expect(response.headers()['cache-control']).toContain('immutable')
    expectSecurityHeaders(response)
  })

  test('are sent with API responses', async ({ request }) => {
    const response = await request.get('/api/v1/health')

    expect(response.ok()).toBe(true)
    expectSecurityHeaders(response)
  })
})
