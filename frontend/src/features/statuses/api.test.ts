import { validateStatusName } from './api'

describe('validateStatusName', () => {
  it('accepts names of 1-50 characters after trimming', () => {
    expect(validateStatusName('Review')).toBeNull()
    expect(validateStatusName('  Review  ')).toBeNull()
    expect(validateStatusName('a'.repeat(50))).toBeNull()
  })

  it('rejects blank names', () => {
    expect(validateStatusName('')).toBe('Enter a column name.')
    expect(validateStatusName('   ')).toBe('Enter a column name.')
  })

  it('rejects names over 50 characters', () => {
    expect(validateStatusName('a'.repeat(51))).toBe('Column names must be 50 characters or fewer.')
    // Surrounding spaces don't count.
    expect(validateStatusName(` ${'a'.repeat(50)} `)).toBeNull()
  })
})
