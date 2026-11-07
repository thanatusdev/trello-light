import { z } from 'zod'

/** Task filters shared by the board and the list, mirroring the API's query params. */
export interface TaskFilters {
  status_id?: string
  assignee_id?: string
  due_after?: string
  due_before?: string
  is_completed?: boolean
  search?: string
}

/** One parser per param, so a single bad value is dropped without losing the rest. */
const fieldParsers = {
  status_id: z.uuid(),
  assignee_id: z.uuid(),
  due_after: z.iso.date(),
  due_before: z.iso.date(),
  is_completed: z.enum(['true', 'false']).transform((value) => value === 'true'),
  search: z.string().trim().min(1).max(200),
} satisfies { [K in keyof TaskFilters]-?: z.ZodType<TaskFilters[K]> }

export const FILTER_KEYS = Object.keys(fieldParsers) as (keyof TaskFilters)[]

export function parseFilters(params: URLSearchParams): TaskFilters {
  const entries = FILTER_KEYS.flatMap((key) => {
    const raw = params.get(key)
    if (raw === null) return []
    const result = fieldParsers[key].safeParse(raw)
    return result.success ? [[key, result.data] as const] : []
  })
  return Object.fromEntries(entries)
}

/** `params` with the filter keys replaced by `filters`. Changing filters resets `page`. */
export function applyFilters(params: URLSearchParams, filters: TaskFilters): URLSearchParams {
  const next = new URLSearchParams(params)
  next.delete('page')
  for (const key of FILTER_KEYS) {
    const value = filters[key]
    if (value === undefined) next.delete(key)
    else next.set(key, String(value))
  }
  return next
}

/** Stable string form, used to tell whether the store and the URL disagree. */
export function filtersKey(filters: TaskFilters): string {
  return FILTER_KEYS.map((key) => `${key}=${String(filters[key] ?? '')}`).join('&')
}

/**
 * Query params for the API. The board leaves out `status_id`: the server would still
 * return every column, so the board hides the other columns itself.
 */
export function toQuery(filters: TaskFilters, { includeStatus }: { includeStatus: boolean }) {
  const query = { ...filters }
  if (!includeStatus) delete query.status_id
  return query
}

export function countActive(filters: TaskFilters): number {
  return FILTER_KEYS.filter((key) => filters[key] !== undefined).length
}
