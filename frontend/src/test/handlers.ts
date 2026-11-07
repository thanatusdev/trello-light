import { http, HttpResponse } from 'msw'

import type { Task } from '@/features/tasks/api'

import { db, newId, users } from './db'

export const API = '/api/v1'

export const demoUser = {
  id: '6f1c2a3e-0000-4000-8000-000000000001',
  email: 'alice@example.com',
  full_name: 'Alice Smith',
  is_active: true,
  created_at: '2026-11-01T10:00:00Z',
}

export const tokens = {
  initial: { access_token: 'access-1', refresh_token: 'refresh-1', token_type: 'bearer' },
  refreshed: { access_token: 'access-2', refresh_token: 'refresh-2', token_type: 'bearer' },
} as const

const unauthorized = () =>
  HttpResponse.json(
    { detail: 'Could not validate credentials' },
    { status: 401, headers: { 'WWW-Authenticate': 'Bearer' } },
  )

/** Default happy-path handlers; individual tests override them with `server.use`. */
export const handlers = [
  http.post(`${API}/auth/register`, async ({ request }) => {
    const body = (await request.json()) as { email: string; full_name: string; password: string }
    const email = body.email.trim().toLowerCase()
    if (email === demoUser.email || db.accounts.some((a) => a.email === email)) {
      return HttpResponse.json({ detail: 'Email is already registered' }, { status: 409 })
    }
    db.accounts.push({ email, password: body.password })
    return HttpResponse.json(
      { ...demoUser, id: newId('6f1c2a3e'), email, full_name: body.full_name },
      { status: 201 },
    )
  }),
  http.post(`${API}/auth/login`, async ({ request }) => {
    const form = new URLSearchParams(await request.text())
    const email = form.get('username')
    const password = form.get('password')
    const known =
      (email === demoUser.email && password === 'Demo1234!') ||
      db.accounts.some((a) => a.email === email && a.password === password)
    if (known) return HttpResponse.json(tokens.initial)
    return HttpResponse.json({ detail: 'Incorrect email or password' }, { status: 401 })
  }),
  http.post(`${API}/auth/refresh`, async ({ request }) => {
    const body = (await request.json()) as { refresh_token?: string }
    return body.refresh_token?.startsWith('refresh-')
      ? HttpResponse.json(tokens.refreshed)
      : unauthorized()
  }),
  http.post(`${API}/auth/logout`, () => new HttpResponse(null, { status: 204 })),
  http.get(`${API}/auth/me`, ({ request }) =>
    request.headers.get('Authorization')?.startsWith('Bearer access-')
      ? HttpResponse.json(demoUser)
      : unauthorized(),
  ),
  ...boardHandlers(),
]

export { unauthorized }

const notFound = (what: string) =>
  HttpResponse.json({ detail: `${what} not found` }, { status: 404 })
const stale = () =>
  HttpResponse.json(
    { detail: 'Neighbours do not match the current order; refresh and retry' },
    { status: 409 },
  )

function matches(task: Task, query: URLSearchParams): boolean {
  const status = query.get('status_id')
  const assignee = query.get('assignee_id')
  const before = query.get('due_before')
  const after = query.get('due_after')
  const completed = query.get('is_completed')
  const search = query.get('search')?.trim().toLowerCase()
  if (status && task.status_id !== status) return false
  if (assignee && task.assignee?.id !== assignee) return false
  if (before && (!task.due_date || task.due_date > before)) return false
  if (after && (!task.due_date || task.due_date < after)) return false
  if (completed && (task.completed_at !== null) !== (completed === 'true')) return false
  if (search && !task.title.toLowerCase().includes(search)) return false
  return true
}

const byPosition = (a: { position: number }, b: { position: number }) => a.position - b.position

/** Same placement rules as the backend's `place()`, minus rebalancing. */
function place(
  siblings: { id: string; position: number }[],
  itemId: string,
  afterId?: string | null,
  beforeId?: string | null,
): number | null {
  const others = siblings.filter((s) => s.id !== itemId).sort(byPosition)
  const indexOf = (id: string) => others.findIndex((s) => s.id === id)
  let index = others.length
  if (beforeId) {
    index = indexOf(beforeId)
    if (index === -1 || (afterId && indexOf(afterId) + 1 !== index)) return null
  } else if (afterId) {
    if (indexOf(afterId) === -1) return null
    index = indexOf(afterId) + 1
  }
  const prev = others[index - 1]?.position ?? null
  const next = others[index]?.position ?? null
  if (next === null) return prev === null ? 1024 : prev + 1024
  return ((prev ?? 0) + next) / 2
}

function assigneeFor(id: string | null | undefined) {
  const user = users.find((u) => u.id === id)
  return user ? { id: user.id, full_name: user.full_name } : null
}

function boardHandlers() {
  return [
    http.get(`${API}/users`, () =>
      HttpResponse.json({ items: users, total: users.length, page: 1, size: 100, pages: 1 }),
    ),

    http.get(`${API}/board`, ({ request }) => {
      const query = new URL(request.url).searchParams
      return HttpResponse.json({
        columns: [...db.statuses].sort(byPosition).map((status) => ({
          id: status.id,
          name: status.name,
          position: status.position,
          is_done: status.is_done,
          tasks: db.tasks
            .filter((t) => t.status_id === status.id && matches(t, query))
            .sort(byPosition),
        })),
      })
    }),

    http.get(`${API}/tasks`, ({ request }) => {
      const query = new URL(request.url).searchParams
      const page = Number(query.get('page') ?? 1)
      const size = Number(query.get('size') ?? 20)
      const all = db.tasks
        .filter((t) => matches(t, query))
        .sort((a, b) => b.created_at.localeCompare(a.created_at))
      return HttpResponse.json({
        items: all.slice((page - 1) * size, page * size),
        total: all.length,
        page,
        size,
        pages: Math.ceil(all.length / size),
      })
    }),

    http.get(`${API}/tasks/:id`, ({ params }) => {
      const task = db.tasks.find((t) => t.id === params.id)
      return task ? HttpResponse.json(task) : notFound('Task')
    }),

    http.post(`${API}/tasks`, async ({ request }) => {
      const body = (await request.json()) as {
        title: string
        description?: string | null
        status_id: string
        assignee_id?: string | null
        due_date?: string | null
      }
      const status = db.statuses.find((s) => s.id === body.status_id)
      if (!status) return HttpResponse.json({ detail: 'Status not found' }, { status: 422 })
      const now = new Date().toISOString()
      const task: Task = {
        id: newId(),
        title: body.title,
        description: body.description ?? null,
        status_id: status.id,
        assignee: assigneeFor(body.assignee_id),
        created_by_id: users[0]?.id ?? '',
        due_date: body.due_date ?? null,
        position:
          place(
            db.tasks.filter((t) => t.status_id === status.id),
            '',
          ) ?? 1024,
        completed_at: status.is_done ? now : null,
        created_at: now,
        updated_at: now,
      }
      db.tasks.push(task)
      return HttpResponse.json(task, { status: 201 })
    }),

    http.patch(`${API}/tasks/:id`, async ({ params, request }) => {
      const task = db.tasks.find((t) => t.id === params.id)
      if (!task) return notFound('Task')
      Object.assign(task, (await request.json()) as Partial<Task>)
      return HttpResponse.json(task)
    }),

    http.put(`${API}/tasks/:id/assignee`, async ({ params, request }) => {
      const task = db.tasks.find((t) => t.id === params.id)
      if (!task) return notFound('Task')
      const { assignee_id } = (await request.json()) as { assignee_id: string | null }
      task.assignee = assigneeFor(assignee_id)
      return HttpResponse.json(task)
    }),

    http.post(`${API}/tasks/:id/move`, async ({ params, request }) => {
      const task = db.tasks.find((t) => t.id === params.id)
      if (!task) return notFound('Task')
      const body = (await request.json()) as {
        status_id: string
        after_id?: string
        before_id?: string
      }
      const status = db.statuses.find((s) => s.id === body.status_id)
      if (!status) return HttpResponse.json({ detail: 'Status not found' }, { status: 422 })
      const siblings = db.tasks.filter((t) => t.status_id === status.id)
      const position = place(siblings, task.id, body.after_id, body.before_id)
      if (position === null) return stale()
      task.status_id = status.id
      task.position = position
      task.completed_at = status.is_done ? (task.completed_at ?? new Date().toISOString()) : null
      return HttpResponse.json(task)
    }),

    http.delete(`${API}/tasks/:id`, ({ params }) => {
      const before = db.tasks.length
      db.tasks = db.tasks.filter((t) => t.id !== params.id)
      return db.tasks.length === before ? notFound('Task') : new HttpResponse(null, { status: 204 })
    }),

    http.post(`${API}/statuses`, async ({ request }) => {
      const body = (await request.json()) as { name: string; is_done?: boolean }
      const name = body.name.trim()
      if (db.statuses.some((s) => s.name.toLowerCase() === name.toLowerCase())) {
        return HttpResponse.json(
          { detail: `A column named "${name}" already exists` },
          { status: 409 },
        )
      }
      const status = {
        id: newId('5a7e0000'),
        name,
        position: place(db.statuses, '') ?? 1024,
        is_done: body.is_done ?? false,
        created_at: new Date().toISOString(),
      }
      db.statuses.push(status)
      return HttpResponse.json(status, { status: 201 })
    }),

    http.patch(`${API}/statuses/:id`, async ({ params, request }) => {
      const status = db.statuses.find((s) => s.id === params.id)
      if (!status) return notFound('Status')
      const name = ((await request.json()) as { name: string }).name.trim()
      if (
        db.statuses.some((s) => s.id !== status.id && s.name.toLowerCase() === name.toLowerCase())
      ) {
        return HttpResponse.json(
          { detail: `A column named "${name}" already exists` },
          { status: 409 },
        )
      }
      status.name = name
      return HttpResponse.json(status)
    }),

    http.post(`${API}/statuses/:id/move`, async ({ params, request }) => {
      const status = db.statuses.find((s) => s.id === params.id)
      if (!status) return notFound('Status')
      const body = (await request.json()) as { after_id?: string; before_id?: string }
      const position = place(db.statuses, status.id, body.after_id, body.before_id)
      if (position === null) return stale()
      status.position = position
      return HttpResponse.json(status)
    }),

    http.delete(`${API}/statuses/:id`, ({ params }) => {
      if (!db.statuses.some((s) => s.id === params.id)) return notFound('Status')
      if (db.tasks.some((t) => t.status_id === params.id)) {
        return HttpResponse.json(
          { detail: 'Status still has tasks; move or delete them first' },
          { status: 409 },
        )
      }
      db.statuses = db.statuses.filter((s) => s.id !== params.id)
      return new HttpResponse(null, { status: 204 })
    }),
  ]
}
