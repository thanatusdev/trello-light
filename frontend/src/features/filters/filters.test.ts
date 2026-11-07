import { applyFilters, countActive, parseFilters, toQuery } from './filters'

const STATUS = '8d4c3c1e-7a39-4f8a-9d55-0b1c9d1f4a10'
const USER = '6f1c2a3e-0000-4000-8000-000000000001'

describe('parseFilters', () => {
  it('reads every supported filter', () => {
    const params = new URLSearchParams({
      status_id: STATUS,
      assignee_id: USER,
      due_after: '2026-11-01',
      due_before: '2026-11-30',
      is_completed: 'false',
      search: ' readme ',
    })
    expect(parseFilters(params)).toEqual({
      status_id: STATUS,
      assignee_id: USER,
      due_after: '2026-11-01',
      due_before: '2026-11-30',
      is_completed: false,
      search: 'readme',
    })
  })

  it('drops invalid values instead of failing', () => {
    const params = new URLSearchParams({
      status_id: 'not-a-uuid',
      due_after: 'yesterday',
      is_completed: 'maybe',
      search: '   ',
      unrelated: 'x',
    })
    expect(parseFilters(params)).toEqual({})
  })

  it('drops a search longer than the API allows', () => {
    expect(parseFilters(new URLSearchParams({ search: 'a'.repeat(201) }))).toEqual({})
  })
})

describe('applyFilters', () => {
  it('writes filters, keeps unrelated params, and resets the page', () => {
    const current = new URLSearchParams({ task: 'abc', page: '3', size: '50', search: 'old' })
    const next = applyFilters(current, { is_completed: true, assignee_id: USER })
    expect(Object.fromEntries(next)).toEqual({
      task: 'abc',
      size: '50',
      assignee_id: USER,
      is_completed: 'true',
    })
  })

  it('round-trips through parseFilters', () => {
    const filters = { status_id: STATUS, due_before: '2026-12-01', search: 'x' }
    expect(parseFilters(applyFilters(new URLSearchParams(), filters))).toEqual(filters)
  })
})

describe('toQuery', () => {
  it('omits the status filter for the board, which hides columns client-side instead', () => {
    expect(toQuery({ status_id: STATUS, search: 'x' }, { includeStatus: false })).toEqual({
      search: 'x',
    })
    expect(toQuery({ status_id: STATUS }, { includeStatus: true })).toEqual({ status_id: STATUS })
  })
})

describe('countActive', () => {
  it('counts the filters that are set', () => {
    expect(countActive({})).toBe(0)
    expect(countActive({ search: 'x', is_completed: false })).toBe(2)
  })
})
