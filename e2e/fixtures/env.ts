/** Test configuration; defaults match the e2e stack and its seed data. */
export const env = {
  baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:8081',
  email: process.env.E2E_USER_EMAIL ?? 'alice@example.com',
  password: process.env.E2E_USER_PASSWORD ?? 'Demo1234!',
  userName: process.env.E2E_USER_NAME ?? 'Alice Johnson',
  otherUserName: process.env.E2E_OTHER_USER_NAME ?? 'Bob Martinez',
}

/** Where the setup project saves the signed-in browser state. */
export const STORAGE_STATE = '.auth/user.json'

/** localStorage key the app persists the refresh token under. */
export const AUTH_STORAGE_KEY = 'trello-light-auth'

/** Seeded columns, in board order. Tests never rename, move or delete these. */
export const SEEDED = { todo: 'To Do', inProgress: 'In Progress', done: 'Done' } as const
