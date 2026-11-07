import { makeTaskSchema, utcToday } from './schema'

const STATUS = '8d4c3c1e-7a39-4f8a-9d55-0b1c9d1f4a10'
const USER = '6f1c2a3e-0000-4000-8000-000000000001'
const TODAY = '2026-11-06'

const valid = {
  title: 'Write the README',
  description: '',
  status_id: STATUS,
  assignee_id: null,
  due_date: null,
}

const schema = makeTaskSchema({ today: TODAY })

function errorsFor(input: unknown, s = schema): Record<string, string> {
  const result = s.safeParse(input)
  if (result.success) return {}
  return Object.fromEntries(result.error.issues.map((i) => [String(i.path[0]), i.message]))
}

describe('task form schema', () => {
  it('accepts a minimal task and normalises it', () => {
    expect(schema.parse({ ...valid, title: '  Write the README  ' })).toEqual({
      title: 'Write the README',
      description: null,
      status_id: STATUS,
      assignee_id: null,
      due_date: null,
    })
  })

  it('keeps a trimmed description, an assignee and a due date', () => {
    expect(
      schema.parse({ ...valid, description: '  notes ', assignee_id: USER, due_date: TODAY }),
    ).toMatchObject({ description: 'notes', assignee_id: USER, due_date: TODAY })
  })

  describe('title', () => {
    it('is required', () => {
      expect(errorsFor({ ...valid, title: '' })).toEqual({ title: 'Enter a title.' })
    })

    it('cannot be only whitespace', () => {
      expect(errorsFor({ ...valid, title: '   ' })).toEqual({ title: 'Enter a title.' })
    })

    it('allows exactly 200 characters after trimming', () => {
      expect(errorsFor({ ...valid, title: ` ${'a'.repeat(200)} ` })).toEqual({})
    })

    it('rejects more than 200 characters', () => {
      expect(errorsFor({ ...valid, title: 'a'.repeat(201) })).toEqual({
        title: 'Title must be 200 characters or fewer.',
      })
    })
  })

  describe('description', () => {
    it('allows 5000 characters', () => {
      expect(errorsFor({ ...valid, description: 'a'.repeat(5000) })).toEqual({})
    })

    it('rejects more than 5000 characters', () => {
      expect(errorsFor({ ...valid, description: 'a'.repeat(5001) })).toEqual({
        description: 'Description must be 5000 characters or fewer.',
      })
    })
  })

  describe('due date', () => {
    it('allows today and later', () => {
      expect(errorsFor({ ...valid, due_date: TODAY })).toEqual({})
      expect(errorsFor({ ...valid, due_date: '2027-01-01' })).toEqual({})
    })

    it('rejects a past date', () => {
      expect(errorsFor({ ...valid, due_date: '2026-11-05' })).toEqual({
        due_date: "Due date can't be in the past.",
      })
    })

    it('keeps an existing past date unchanged when editing', () => {
      const editing = makeTaskSchema({ today: TODAY, originalDueDate: '2026-10-01' })
      expect(errorsFor({ ...valid, due_date: '2026-10-01' }, editing)).toEqual({})
      expect(errorsFor({ ...valid, due_date: '2026-10-02' }, editing)).toEqual({
        due_date: "Due date can't be in the past.",
      })
    })

    it('rejects something that is not an ISO date', () => {
      expect(errorsFor({ ...valid, due_date: '06/11/2026' })).toHaveProperty('due_date')
    })
  })

  it('requires a column', () => {
    expect(errorsFor({ ...valid, status_id: '' })).toEqual({ status_id: 'Choose a column.' })
  })

  it('rejects an assignee that is not a user id', () => {
    expect(errorsFor({ ...valid, assignee_id: 'bob' })).toHaveProperty('assignee_id')
  })
})

describe('utcToday', () => {
  it('uses the UTC calendar date, like the server', () => {
    // 23:30 on the 6th in New York is already the 7th in UTC.
    expect(utcToday(new Date('2026-11-06T23:30:00-05:00'))).toBe('2026-11-07')
  })
})
