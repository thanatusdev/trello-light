import { fakeJwt } from '@/test/jwt'

import { tokenSubject } from './jwt'

describe('tokenSubject', () => {
  it("reads the token's subject", () => {
    expect(tokenSubject(fakeJwt({ sub: 'user-1', type: 'refresh' }))).toBe('user-1')
  })

  it('decodes base64url and UTF-8 payloads', () => {
    // These characters encode to '-' / '_' in base64url, and 'ü' is multi-byte.
    expect(tokenSubject(fakeJwt({ sub: 'ü?>?~~~' }))).toBe('ü?>?~~~')
  })

  it.each([
    ['no token', null],
    ['an opaque token', 'refresh-1'],
    ['a malformed payload', 'a.!!!.c'],
    ['a payload that is not JSON', `a.${btoa('nope')}.c`],
    ['a payload without a subject', fakeJwt({ type: 'refresh' })],
    ['a non-string subject', fakeJwt({ sub: 42 })],
  ])('returns null for %s', (_label, token) => {
    expect(tokenSubject(token)).toBeNull()
  })
})
