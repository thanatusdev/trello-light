/**
 * The `sub` claim of a JWT, or null if the token isn't a JWT or has none. The signature is
 * NOT verified: use this only to tell sessions apart, never to trust who the user is.
 */
export function tokenSubject(token: string | null): string | null {
  const payload = token?.split('.')[1]
  if (!payload) return null
  try {
    const base64 = payload.replace(/-/g, '+').replace(/_/g, '/')
    const bytes = Uint8Array.from(atob(base64), (char) => char.charCodeAt(0))
    const claims: unknown = JSON.parse(new TextDecoder().decode(bytes))
    const sub = (claims as { sub?: unknown } | null)?.sub
    return typeof sub === 'string' ? sub : null
  } catch {
    return null
  }
}
