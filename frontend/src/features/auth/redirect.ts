export interface RedirectState {
  from?: unknown
}

/** Where to go after signing in. Only same-app paths are allowed, to avoid open redirects. */
export function redirectTarget(state: unknown): string {
  const from = (state as RedirectState | null)?.from
  if (typeof from === 'string' && from.startsWith('/') && !from.startsWith('//')) return from
  return '/'
}
