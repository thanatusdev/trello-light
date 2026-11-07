import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiClient } from '@/api/client'
import { toApiError } from '@/api/errors'
import { boardKeys } from '@/features/board/api'

export async function createStatus(body: { name: string; is_done: boolean }): Promise<void> {
  const { error, response } = await apiClient.POST('/api/v1/statuses', { body })
  if (!response.ok) throw toApiError(response, error)
}

export async function renameStatus({ id, name }: { id: string; name: string }): Promise<void> {
  const { error, response } = await apiClient.PATCH('/api/v1/statuses/{status_id}', {
    params: { path: { status_id: id } },
    body: { name },
  })
  if (!response.ok) throw toApiError(response, error)
}

export async function deleteStatus(id: string): Promise<void> {
  const { error, response } = await apiClient.DELETE('/api/v1/statuses/{status_id}', {
    params: { path: { status_id: id } },
  })
  if (!response.ok) throw toApiError(response, error)
}

function useStatusMutation<T>(mutationFn: (variables: T) => Promise<void>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: boardKeys.all }),
  })
}

export const useCreateStatus = () => useStatusMutation(createStatus)
export const useRenameStatus = () => useStatusMutation(renameStatus)
/** Not optimistic: a column that still has tasks is refused (409) and the dialog says why. */
export const useDeleteStatus = () => useStatusMutation(deleteStatus)

/** Column name rules from the backend: trimmed, 1-50 characters. */
export function validateStatusName(name: string): string | null {
  const trimmed = name.trim()
  if (trimmed.length === 0) return 'Enter a column name.'
  if (trimmed.length > 50) return 'Column names must be 50 characters or fewer.'
  return null
}
