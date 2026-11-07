import { z } from 'zod'

import { apiClient, tokenResponseSchema } from '@/api/client'
import { toApiError } from '@/api/errors'

export const userSchema = z.object({
  id: z.uuid(),
  email: z.string(),
  full_name: z.string(),
  is_active: z.boolean(),
  created_at: z.string(),
})

export type User = z.infer<typeof userSchema>
export type Tokens = z.infer<typeof tokenResponseSchema>

export interface Credentials {
  email: string
  password: string
}

export async function login({ email, password }: Credentials): Promise<Tokens> {
  // The backend uses OAuth2's password form: form-encoded, with the email as `username`.
  const { data, error, response } = await apiClient.POST('/api/v1/auth/login', {
    body: { username: email, password, scope: '' },
    bodySerializer: (body) =>
      new URLSearchParams({ username: body.username, password: body.password }),
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
  if (!response.ok) throw toApiError(response, error)
  return tokenResponseSchema.parse(data)
}

export interface Registration {
  email: string
  full_name: string
  password: string
}

export async function registerAccount(body: Registration): Promise<User> {
  const { data, error, response } = await apiClient.POST('/api/v1/auth/register', { body })
  if (!response.ok) throw toApiError(response, error)
  return userSchema.parse(data)
}

export async function fetchMe(): Promise<User> {
  const { data, error, response } = await apiClient.GET('/api/v1/auth/me')
  if (!response.ok) throw toApiError(response, error)
  return userSchema.parse(data)
}

/**
 * Revoke the session on the server. Best effort: the browser forgets the tokens either way,
 * so failures (offline, 5xx) are ignored.
 */
export async function logout(refreshToken: string): Promise<void> {
  try {
    await apiClient.POST('/api/v1/auth/logout', { body: { refresh_token: refreshToken } })
  } catch {
    // Network error: nothing more the client can do.
  }
}
