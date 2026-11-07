import { ApiError, errorMessage, rateLimitMessage, toApiError } from './errors'

describe('toApiError', () => {
  it('uses a string detail as the message', () => {
    const error = toApiError(new Response(null, { status: 409 }), { detail: 'Name taken' })

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 409, message: 'Name taken', retryAfter: null })
  })

  it('joins FastAPI validation messages', () => {
    const body = { detail: [{ msg: 'Field required' }, { msg: 'Too long' }] }

    expect(toApiError(new Response(null, { status: 422 }), body).message).toBe(
      'Field required; Too long',
    )
  })

  it('reads Retry-After in seconds', () => {
    const response = new Response(null, { status: 429, headers: { 'Retry-After': '42' } })

    expect(toApiError(response, { detail: 'Slow down' }).retryAfter).toBe(42)
  })

  it('falls back to the status text when there is no detail', () => {
    const response = new Response(null, { status: 500, statusText: 'Server Error' })

    expect(toApiError(response, undefined).message).toBe('Request failed (500 Server Error)')
  })
})

describe('rateLimitMessage', () => {
  it('says how long to wait', () => {
    expect(rateLimitMessage(30)).toBe('Too many requests. Try again in 30 seconds.')
    expect(rateLimitMessage(1)).toBe('Too many requests. Try again in 1 second.')
  })

  it('names what was rate limited', () => {
    expect(rateLimitMessage(5, 'sign-in attempts')).toBe(
      'Too many sign-in attempts. Try again in 5 seconds.',
    )
  })

  it('falls back to a vague delay without Retry-After', () => {
    expect(rateLimitMessage(null)).toBe('Too many requests. Try again in a moment.')
  })
})

describe('errorMessage', () => {
  it('formats rate limiting with the retry delay', () => {
    expect(errorMessage(new ApiError(429, 'Rate limit exceeded', 7))).toBe(
      'Too many requests. Try again in 7 seconds.',
    )
  })

  it("uses the API's message for other API errors", () => {
    expect(errorMessage(new ApiError(409, 'Name taken'))).toBe('Name taken')
  })

  it('explains network failures', () => {
    expect(errorMessage(new TypeError('Failed to fetch'))).toBe(
      "Can't reach the server. Check your connection and try again.",
    )
  })

  it('falls back for anything else', () => {
    expect(errorMessage(new Error('Kaboom'))).toBe('Kaboom')
    expect(errorMessage('weird')).toBe('Something went wrong.')
  })
})
