import { z } from 'zod'

/** Today's date as `YYYY-MM-DD` in UTC: the server validates due dates against UTC. */
export function utcToday(now: Date = new Date()): string {
  return now.toISOString().slice(0, 10)
}

/** Whether `date` may be chosen as a due date (also used to disable calendar days). */
export function isAllowedDueDate(
  date: string,
  { today, originalDueDate }: { today: string; originalDueDate?: string | null },
): boolean {
  // ISO dates compare correctly as strings. The server only checks a date that changed.
  return date >= today || date === originalDueDate
}

interface TaskSchemaOptions {
  /** The task's current due date when editing; it may stay even if it is now past. */
  originalDueDate?: string | null
  today?: string
}

/** Mirrors the backend rules in `domain/tasks.py`. */
export function makeTaskSchema({
  originalDueDate = null,
  today = utcToday(),
}: TaskSchemaOptions = {}) {
  return z.object({
    title: z
      .string()
      .trim()
      .min(1, 'Enter a title.')
      .max(200, 'Title must be 200 characters or fewer.'),
    description: z
      .string()
      .trim()
      .max(5000, 'Description must be 5000 characters or fewer.')
      .transform((value) => value || null),
    status_id: z.uuid('Choose a column.'),
    assignee_id: z.uuid('Choose a valid assignee.').nullable(),
    due_date: z.iso
      .date('Enter a valid date.')
      .refine((date) => isAllowedDueDate(date, { today, originalDueDate }), {
        message: "Due date can't be in the past.",
      })
      .nullable(),
  })
}

export type TaskSchema = ReturnType<typeof makeTaskSchema>
export type TaskFormInput = z.input<TaskSchema>
export type TaskFormValues = z.output<TaskSchema>
