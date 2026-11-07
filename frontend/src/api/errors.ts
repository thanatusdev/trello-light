/** A non-2xx API response, normalised from FastAPI's `{detail}` error body. */
export class ApiError extends Error {
  readonly status: number
  /** Seconds to wait before retrying, from the `Retry-After` header (429 responses). */
  readonly retryAfter: number | null

  constructor(status: number, message: string, retryAfter: number | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.retryAfter = retryAfter
  }
}

function detailMessage(body: unknown): string | null {
  if (typeof body !== 'object' || body === null || !('detail' in body)) return null
  const { detail } = body
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item: unknown) =>
        typeof item === 'object' && item !== null && 'msg' in item ? String(item.msg) : null,
      )
      .filter((msg): msg is string => msg !== null)
    return messages.length > 0 ? messages.join('; ') : null
  }
  return null
}

export function toApiError(response: Response, body: unknown): ApiError {
  const retryAfterHeader = Number(response.headers.get('Retry-After'))
  const retryAfter =
    Number.isFinite(retryAfterHeader) && retryAfterHeader > 0 ? retryAfterHeader : null
  const message =
    detailMessage(body) ?? `Request failed (${response.status} ${response.statusText})`.trim()
  return new ApiError(response.status, message, retryAfter)
}

export const NETWORK_ERROR_MESSAGE = "Can't reach the server. Check your connection and try again."

/** "Too many <what>. Try again in N seconds." from a 429's `retryAfter`. */
export function rateLimitMessage(retryAfter: number | null, what = 'requests'): string {
  if (!retryAfter) return `Too many ${what}. Try again in a moment.`
  return `Too many ${what}. Try again in ${retryAfter} ${retryAfter === 1 ? 'second' : 'seconds'}.`
}

/** A user-facing message for any error thrown by an API call. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.status === 429 ? rateLimitMessage(error.retryAfter) : error.message
  }
  // fetch rejects with a TypeError when the request never reaches the server.
  if (error instanceof TypeError) return NETWORK_ERROR_MESSAGE
  if (error instanceof Error) return error.message
  return 'Something went wrong.'
}
