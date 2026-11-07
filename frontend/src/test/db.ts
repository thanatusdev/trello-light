import type { Task } from '@/features/tasks/api'

/** In-memory backend state for MSW handlers. Reset after every test. */

const uuid = (prefix: string, n: number) =>
  `${prefix}-0000-4000-8000-${String(n).padStart(12, '0')}`

export const ids = {
  alice: '6f1c2a3e-0000-4000-8000-000000000001',
  bob: '6f1c2a3e-0000-4000-8000-000000000002',
  todo: uuid('5a7e0000', 1),
  doing: uuid('5a7e0000', 2),
  done: uuid('5a7e0000', 3),
  readme: uuid('7a5c0000', 1),
  schema: uuid('7a5c0000', 2),
  ship: uuid('7a5c0000', 3),
}

export interface StatusRow {
  id: string
  name: string
  position: number
  is_done: boolean
  created_at: string
}

const STAMP = '2026-11-01T10:00:00Z'

export const users = [
  { id: ids.alice, email: 'alice@example.com', full_name: 'Alice Smith' },
  { id: ids.bob, email: 'bob@example.com', full_name: 'Bob Jones' },
]

function seedStatuses(): StatusRow[] {
  return [
    { id: ids.todo, name: 'To do', position: 1024, is_done: false, created_at: STAMP },
    { id: ids.doing, name: 'Doing', position: 2048, is_done: false, created_at: STAMP },
    { id: ids.done, name: 'Done', position: 3072, is_done: true, created_at: STAMP },
  ]
}

function makeTask(overrides: Partial<Task> & Pick<Task, 'id' | 'title' | 'status_id'>): Task {
  return {
    description: null,
    assignee: null,
    created_by_id: ids.alice,
    due_date: null,
    position: 1024,
    completed_at: null,
    created_at: STAMP,
    updated_at: STAMP,
    ...overrides,
  }
}

function seedTasks(): Task[] {
  return [
    makeTask({
      id: ids.readme,
      title: 'Write the README',
      description: 'Setup and decisions',
      status_id: ids.todo,
      assignee: { id: ids.alice, full_name: 'Alice Smith' },
      due_date: '2030-01-31',
      position: 1024,
    }),
    makeTask({ id: ids.schema, title: 'Design the schema', status_id: ids.todo, position: 2048 }),
    makeTask({
      id: ids.ship,
      title: 'Ship it',
      status_id: ids.done,
      position: 1024,
      completed_at: STAMP,
    }),
  ]
}

export const db = {
  statuses: seedStatuses(),
  tasks: seedTasks(),
  /** Accounts created through `POST /auth/register` (the demo user is always there). */
  accounts: [] as { email: string; password: string }[],
  nextId: 100,
}

export function resetDb() {
  db.statuses = seedStatuses()
  db.tasks = seedTasks()
  db.accounts = []
  db.nextId = 100
}

export function newId(prefix = '9e110000') {
  db.nextId += 1
  return uuid(prefix, db.nextId)
}

export { makeTask }
