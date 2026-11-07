import { readFile } from 'node:fs/promises'

import type { APIRequestContext, APIResponse } from '@playwright/test'

import { AUTH_STORAGE_KEY, STORAGE_STATE } from './env'

export interface Column {
  id: string
  name: string
  is_done: boolean
  tasks: Task[]
}

export interface Task {
  id: string
  title: string
  status_id: string
  assignee: { id: string; full_name: string } | null
  due_date: string | null
  completed_at: string | null
}

export interface User {
  id: string
  email: string
  full_name: string
}

interface Page<T> {
  items: T[]
}

export interface NewTask {
  title: string
  statusId: string
  assigneeId?: string
  dueDate?: string
  description?: string
}

type Method = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'

/** Reads the refresh token the setup project left in the saved browser state. */
export async function storedRefreshToken(): Promise<string> {
  const state = JSON.parse(await readFile(STORAGE_STATE, 'utf8')) as {
    origins: { localStorage: { name: string; value: string }[] }[]
  }
  const raw = state.origins
    .flatMap((origin) => origin.localStorage)
    .find((item) => item.name === AUTH_STORAGE_KEY)?.value
  const token = raw
    ? (JSON.parse(raw) as { state: { refreshToken?: string } }).state.refreshToken
    : undefined
  if (!token) throw new Error(`No refresh token in ${STORAGE_STATE}; did the setup project run?`)
  return token
}

/**
 * Arranges test data through the REST API, as the signed-in user. The e2e stack issues
 * access tokens that live a few seconds, so a 401 refreshes once and retries, like the app.
 */
export class Api {
  private accessToken: string | null = null

  constructor(
    private readonly request: APIRequestContext,
    private refreshToken: string,
  ) {}

  private async refresh(): Promise<void> {
    const response = await this.request.post('/api/v1/auth/refresh', {
      data: { refresh_token: this.refreshToken },
    })
    await expectOk(response, 'refresh')
    const tokens = (await response.json()) as { access_token: string; refresh_token: string }
    this.accessToken = tokens.access_token
    this.refreshToken = tokens.refresh_token
  }

  private async send(method: Method, url: string, data?: unknown): Promise<APIResponse> {
    if (!this.accessToken) await this.refresh()
    const call = () =>
      this.request.fetch(url, {
        method,
        data,
        headers: { Authorization: `Bearer ${this.accessToken ?? ''}` },
      })
    let response = await call()
    if (response.status() === 401) {
      await this.refresh()
      response = await call()
    }
    return response
  }

  private async json<T>(method: Method, url: string, data?: unknown): Promise<T> {
    const response = await this.send(method, url, data)
    await expectOk(response, `${method} ${url}`)
    return (await response.json()) as T
  }

  async columns(): Promise<Column[]> {
    return (await this.json<{ columns: Column[] }>('GET', '/api/v1/board')).columns
  }

  async column(name: string): Promise<Column> {
    const column = (await this.columns()).find((c) => c.name === name)
    if (!column) throw new Error(`No column named "${name}"`)
    return column
  }

  createColumn(name: string, isDone = false): Promise<Column> {
    return this.json('POST', '/api/v1/statuses', { name, is_done: isDone })
  }

  async deleteColumn(id: string): Promise<APIResponse> {
    return this.send('DELETE', `/api/v1/statuses/${id}`)
  }

  createTask(task: NewTask): Promise<Task> {
    return this.json('POST', '/api/v1/tasks', {
      title: task.title,
      status_id: task.statusId,
      assignee_id: task.assigneeId ?? null,
      due_date: task.dueDate ?? null,
      description: task.description ?? null,
    })
  }

  task(id: string): Promise<Task> {
    return this.json('GET', `/api/v1/tasks/${id}`)
  }

  async tasksMatching(search: string): Promise<Task[]> {
    const query = new URLSearchParams({ search, size: '100' })
    return (await this.json<Page<Task>>('GET', `/api/v1/tasks?${query.toString()}`)).items
  }

  async deleteTask(id: string): Promise<APIResponse> {
    return this.send('DELETE', `/api/v1/tasks/${id}`)
  }

  async user(fullName: string): Promise<User> {
    const users = (await this.json<Page<User>>('GET', '/api/v1/users?size=100')).items
    const user = users.find((u) => u.full_name === fullName)
    if (!user) throw new Error(`No user named "${fullName}"`)
    return user
  }

  /** Deletes every task and column whose name contains `marker`. Best effort. */
  async cleanUp(marker: string): Promise<void> {
    for (const task of await this.tasksMatching(marker)) await this.deleteTask(task.id)
    for (const column of await this.columns()) {
      if (column.name.includes(marker)) await this.deleteColumn(column.id)
    }
  }
}

async function expectOk(response: APIResponse, what: string): Promise<void> {
  if (!response.ok()) {
    throw new Error(`${what} failed: ${response.status()} ${await response.text()}`)
  }
}
