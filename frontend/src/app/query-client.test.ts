import { ApiError } from '@/api/errors'

import { createQueryClient } from './query-client'

function retryPolicy() {
  const retry = createQueryClient().getDefaultOptions().queries?.retry
  if (typeof retry !== 'function') throw new Error('expected a retry function')
  return retry
}

describe('query retry policy', () => {
  it('does not retry client errors', () => {
    expect(retryPolicy()(0, new ApiError(404, 'Not found'))).toBe(false)
  })

  it('retries server and network errors twice', () => {
    const retry = retryPolicy()
    expect(retry(0, new ApiError(503, 'Unavailable'))).toBe(true)
    expect(retry(1, new TypeError('Failed to fetch'))).toBe(true)
    expect(retry(2, new TypeError('Failed to fetch'))).toBe(false)
  })
})
