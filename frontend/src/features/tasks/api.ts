import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { z } from 'zod'

import { apiClient } from '@/api/client'
import { toApiError } from '@/api/errors'
import { type TaskFilters, toQuery } from '@/features/filters/filters'

export const taskSchema = z.object({
  id: z.uuid(),
  title: z.string(),
  description: z.string().nullable(),
  status_id: z.uuid(),
  assignee: z.object({ id: z.uuid(), full_name: z.string() }).nullable(),
  created_by_id: z.uuid(),
  due_date: z.string().nullable(),
  position: z.number(),
  completed_at: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
})

export type Task = z.infer<typeof taskSchema>

const taskPageSchema = z.object({
  items: z.array(taskSchema),
  total: z.number(),
  page: z.number(),
  size: z.number(),
  pages: z.number(),
})

export type TaskPage = z.infer<typeof taskPageSchema>

export const taskKeys = {
  all: ['tasks'] as const,
  list: (params: object) => ['tasks', 'list', params] as const,
  detail: (id: string) => ['tasks', 'detail', id] as const,
}

export interface TaskListParams {
  filters: TaskFilters
  page: number
  size: number
}

export async function fetchTasks({ filters, page, size }: TaskListParams): Promise<TaskPage> {
  const { data, error, response } = await apiClient.GET('/api/v1/tasks', {
    params: { query: { ...toQuery(filters, { includeStatus: true }), page, size } },
  })
  if (!response.ok) throw toApiError(response, error)
  return taskPageSchema.parse(data)
}

export function useTasks(params: TaskListParams) {
  return useQuery({
    queryKey: taskKeys.list(params),
    queryFn: () => fetchTasks(params),
    placeholderData: keepPreviousData,
  })
}

export async function fetchTask(id: string): Promise<Task> {
  const { data, error, response } = await apiClient.GET('/api/v1/tasks/{task_id}', {
    params: { path: { task_id: id } },
  })
  if (!response.ok) throw toApiError(response, error)
  return taskSchema.parse(data)
}

export function useTask(id: string | null) {
  return useQuery({
    queryKey: taskKeys.detail(id ?? ''),
    queryFn: () => fetchTask(id ?? ''),
    enabled: id !== null,
  })
}

export interface CreateTaskBody {
  title: string
  description: string | null
  status_id: string
  assignee_id: string | null
  due_date: string | null
}

export async function createTask(body: CreateTaskBody): Promise<Task> {
  const { data, error, response } = await apiClient.POST('/api/v1/tasks', { body })
  if (!response.ok) throw toApiError(response, error)
  return taskSchema.parse(data)
}

export interface UpdateTaskBody {
  title?: string
  description?: string | null
  due_date?: string | null
}

export async function updateTask(id: string, body: UpdateTaskBody): Promise<Task> {
  const { data, error, response } = await apiClient.PATCH('/api/v1/tasks/{task_id}', {
    params: { path: { task_id: id } },
    body,
  })
  if (!response.ok) throw toApiError(response, error)
  return taskSchema.parse(data)
}

export async function assignTask(id: string, assigneeId: string | null): Promise<Task> {
  const { data, error, response } = await apiClient.PUT('/api/v1/tasks/{task_id}/assignee', {
    params: { path: { task_id: id } },
    body: { assignee_id: assigneeId },
  })
  if (!response.ok) throw toApiError(response, error)
  return taskSchema.parse(data)
}

export interface MoveTaskBody {
  status_id: string
  after_id?: string
  before_id?: string
}

export async function moveTask(id: string, body: MoveTaskBody): Promise<Task> {
  const { data, error, response } = await apiClient.POST('/api/v1/tasks/{task_id}/move', {
    params: { path: { task_id: id } },
    body,
  })
  if (!response.ok) throw toApiError(response, error)
  return taskSchema.parse(data)
}

export async function deleteTask(id: string): Promise<void> {
  const { error, response } = await apiClient.DELETE('/api/v1/tasks/{task_id}', {
    params: { path: { task_id: id } },
  })
  if (!response.ok) throw toApiError(response, error)
}
