import { z } from 'zod'

/** Mirrors the backend value objects in `app/domain/users.py`. */
export const FULL_NAME_MAX_LENGTH = 100
export const PASSWORD_MIN_LENGTH = 8
/** bcrypt only uses the first 72 bytes, so the backend refuses longer passwords. */
export const PASSWORD_MAX_BYTES = 72

const encoder = new TextEncoder()

/** Unicode code points, which is what Python's len() counts on the backend. */
function codePointLength(value: string): number {
  return Array.from(value).length
}

export const registerSchema = z
  .object({
    full_name: z
      .string()
      .trim()
      .min(1, 'Enter your name.')
      .max(FULL_NAME_MAX_LENGTH, `Names must be ${FULL_NAME_MAX_LENGTH} characters or fewer.`),
    email: z.email('Enter a valid email address.'),
    password: z
      .string()
      .refine(
        (value) => codePointLength(value) >= PASSWORD_MIN_LENGTH,
        `Use at least ${PASSWORD_MIN_LENGTH} characters.`,
      )
      .refine(
        (value) => encoder.encode(value).length <= PASSWORD_MAX_BYTES,
        `Use at most ${PASSWORD_MAX_BYTES} bytes (fewer characters if you use accents or emoji).`,
      ),
    confirm_password: z.string(),
  })
  .refine((values) => values.password === values.confirm_password, {
    path: ['confirm_password'],
    message: "Passwords don't match.",
  })

export type RegisterValues = z.input<typeof registerSchema>
export type RegisterData = z.output<typeof registerSchema>
