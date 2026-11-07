import { registerSchema } from './register-schema'

const valid = {
  full_name: 'Dana Scully',
  email: 'dana@example.com',
  password: 'trustno1!',
  confirm_password: 'trustno1!',
}

function messages(values: Partial<typeof valid>) {
  const result = registerSchema.safeParse({ ...valid, ...values })
  return result.success ? [] : result.error.issues.map((issue) => issue.message)
}

describe('registerSchema', () => {
  it('accepts valid details and trims the name', () => {
    expect(registerSchema.parse({ ...valid, full_name: '  Dana Scully ' }).full_name).toBe(
      'Dana Scully',
    )
  })

  it('requires a name of at most 100 characters', () => {
    expect(messages({ full_name: '   ' })).toEqual(['Enter your name.'])
    expect(messages({ full_name: 'a'.repeat(100) })).toEqual([])
    expect(messages({ full_name: 'a'.repeat(101) })).toEqual([
      'Names must be 100 characters or fewer.',
    ])
  })

  it('requires a valid email', () => {
    expect(messages({ email: 'not-an-email' })).toEqual(['Enter a valid email address.'])
  })

  it('requires at least 8 characters', () => {
    expect(messages({ password: 'short', confirm_password: 'short' })).toEqual([
      'Use at least 8 characters.',
    ])
    // Characters, not UTF-16 code units: 8 emoji are 8 characters.
    expect(messages({ password: '🙂'.repeat(7), confirm_password: '🙂'.repeat(7) })).toEqual([
      'Use at least 8 characters.',
    ])
  })

  it('limits the password to 72 bytes of UTF-8, as bcrypt does', () => {
    expect(messages({ password: 'a'.repeat(72), confirm_password: 'a'.repeat(72) })).toEqual([])
    expect(messages({ password: 'a'.repeat(73), confirm_password: 'a'.repeat(73) })).toEqual([
      'Use at most 72 bytes (fewer characters if you use accents or emoji).',
    ])
    // 37 two-byte characters are 74 bytes, though only 37 characters.
    expect(messages({ password: 'é'.repeat(37), confirm_password: 'é'.repeat(37) })).toEqual([
      'Use at most 72 bytes (fewer characters if you use accents or emoji).',
    ])
  })

  it('requires the passwords to match', () => {
    const result = registerSchema.safeParse({ ...valid, confirm_password: 'different!' })

    expect(result.success).toBe(false)
    expect(result.error?.issues).toEqual([
      expect.objectContaining({ path: ['confirm_password'], message: "Passwords don't match." }),
    ])
  })
})
