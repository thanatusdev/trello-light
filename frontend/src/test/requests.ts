import { server } from './server'

export interface RecordedRequest {
  method: string
  path: string
  body: unknown
}

/** JSON bodies are parsed; anything else (e.g. the login form) is kept as text. */
function parseBody(text: string): unknown {
  if (!text) return undefined
  try {
    return JSON.parse(text) as unknown
  } catch {
    return text
  }
}

/**
 * Record mutating API requests (`METHOD /path` + JSON body) from now on. Listeners are
 * removed after each test in `setup.ts`.
 */
export function recordRequests() {
  const requests: RecordedRequest[] = []
  server.events.on('request:start', ({ request }) => {
    if (request.method === 'GET') return
    const entry: RecordedRequest = {
      method: request.method,
      path: new URL(request.url).pathname.replace('/api/v1', ''),
      body: undefined,
    }
    requests.push(entry)
    void request
      .clone()
      .text()
      .then((text) => {
        entry.body = parseBody(text)
      })
  })
  return requests
}
