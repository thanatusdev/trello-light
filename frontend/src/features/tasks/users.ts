import { useQuery } from '@tanstack/react-query'
import { z } from 'zod'

import { apiClient } from '@/api/client'
import { toApiError } from '@/api/errors'

const userSummarySchema = z.object({ id: z.uuid(), email: z.string(), full_name: z.string() })
const userPageSchema = z.object({ items: z.array(userSummarySchema), pages: z.number() })

export type UserSummary = z.infer<typeof userSummarySchema>

/** The API's maximum page size. The users endpoint has no search, so every page is read. */
const PAGE_SIZE = 100

async function fetchUserPage(page: number) {
  const { data, error, response } = await apiClient.GET('/api/v1/users', {
    params: { query: { page, size: PAGE_SIZE } },
  })
  if (!response.ok) throw toApiError(response, error)
  return userPageSchema.parse(data)
}

/** Every active user, ordered by name: the first page says how many more to fetch. */
export async function fetchUsers(): Promise<UserSummary[]> {
  const first = await fetchUserPage(1)
  const rest = await Promise.all(
    Array.from({ length: Math.max(first.pages - 1, 0) }, (_, i) => fetchUserPage(i + 2)),
  )
  return [first, ...rest].flatMap((page) => page.items)
}

/** Active users for the assignee picker and filter, ordered by name. */
export function useUsers() {
  return useQuery({ queryKey: ['users'], queryFn: fetchUsers, staleTime: 5 * 60_000 })
}
