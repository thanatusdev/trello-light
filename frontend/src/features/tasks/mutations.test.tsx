import { QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'

import { createQueryClient } from '@/app/query-client'
import { useAuthStore } from '@/stores/auth-store'
import { ids } from '@/test/db'
import { tokens } from '@/test/handlers'
import { server } from '@/test/server'

import { useTask } from './api'
import { useDeleteTask } from './mutations'

vi.mock('sonner', async (importOriginal) => {
  const actual = await importOriginal<typeof import('sonner')>()
  return { ...actual, toast: { error: vi.fn(), success: vi.fn() } }
})

describe('useDeleteTask', () => {
  it('does not refetch the deleted task, even while something still shows it', async () => {
    useAuthStore.getState().setTokens(tokens.initial)
    const queryClient = createQueryClient({ retry: false })
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )
    // The edit modal can still be mounted (closing) when the delete settles.
    const { result } = renderHook(() => ({ task: useTask(ids.readme), remove: useDeleteTask() }), {
      wrapper,
    })
    await waitFor(() => {
      expect(result.current.task.isSuccess).toBe(true)
    })
    const fetches: string[] = []
    server.events.on('request:start', ({ request }) => {
      if (request.method === 'GET') fetches.push(new URL(request.url).pathname)
    })

    await result.current.remove.mutateAsync(ids.readme)

    // Lists and boards refresh; the deleted task itself would 404 (a console error).
    await waitFor(() => {
      expect(queryClient.isFetching()).toBe(0)
    })
    expect(fetches.filter((path) => path.endsWith(`/tasks/${ids.readme}`))).toEqual([])
  })
})
