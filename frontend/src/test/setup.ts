import '@testing-library/jest-dom/vitest'

import { cleanup } from '@testing-library/react'

import { useAuthStore } from '@/stores/auth-store'

import { resetDb } from './db'
import { server } from './server'

// jsdom has no matchMedia; sonner uses it to follow the system colour scheme.
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string): MediaQueryList =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList,
})

// jsdom gaps that Radix (Select, Popover) and cmdk rely on.
const noop = () => undefined
Object.assign(globalThis, {
  ResizeObserver: class {
    observe = noop
    unobserve = noop
    disconnect = noop
  },
})
Object.assign(Element.prototype, {
  scrollIntoView: noop,
  hasPointerCapture: () => false,
  releasePointerCapture: noop,
})

beforeAll(() => {
  server.listen({ onUnhandledFrame: 'error' })
})

beforeEach(() => {
  window.history.replaceState(null, '', '/')
})

afterEach(() => {
  cleanup()
  server.resetHandlers()
  server.events.removeAllListeners()
  resetDb()
  useAuthStore.getState().clear()
  localStorage.clear()
})

afterAll(() => {
  server.close()
})
