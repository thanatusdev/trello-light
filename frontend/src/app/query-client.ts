import { QueryClient, type QueryClientConfig } from '@tanstack/react-query'

import { ApiError } from '@/api/errors'

type QueryDefaults = NonNullable<NonNullable<QueryClientConfig['defaultOptions']>['queries']>

/** Client errors (4xx) are not transient, so only network and server errors are retried. */
function shouldRetry(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError && error.status < 500) return false
  return failureCount < 2
}

export function createQueryClient(overrides: Partial<QueryDefaults> = {}): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: shouldRetry, refetchOnWindowFocus: false, staleTime: 30_000, ...overrides },
      mutations: { retry: false },
    },
  })
}
