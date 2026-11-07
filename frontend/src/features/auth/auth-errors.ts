import { ApiError, NETWORK_ERROR_MESSAGE, rateLimitMessage } from '@/api/errors'

const GENERIC = 'Something went wrong. Please try again.'

export function loginErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Incorrect email or password.'
    if (error.status === 429) return rateLimitMessage(error.retryAfter, 'sign-in attempts')
    if (error.status === 422) return 'Check your email and password and try again.'
    return GENERIC
  }
  if (error instanceof TypeError) return NETWORK_ERROR_MESSAGE
  return GENERIC
}

/** The account was created, but signing in with it straight away failed. */
export class SignInAfterRegisterError extends Error {
  constructor(cause: unknown) {
    super('Account created, but signing in failed', { cause })
    this.name = 'SignInAfterRegisterError'
  }
}

export function registerErrorMessage(error: unknown): string {
  if (error instanceof SignInAfterRegisterError) {
    return "Your account was created, but we couldn't sign you in. Sign in to continue."
  }
  if (error instanceof ApiError) {
    if (error.status === 409) return 'An account with this email already exists.'
    if (error.status === 429) return rateLimitMessage(error.retryAfter, 'sign-up attempts')
    // The backend's validation messages (e.g. "Invalid email address") are user-facing.
    if (error.status === 422) return error.message
    return GENERIC
  }
  if (error instanceof TypeError) return NETWORK_ERROR_MESSAGE
  return GENERIC
}
