import { computeMove, MIN_GAP, positionBetween, STEP, toNeighbourIds } from './ordering'

const items = (...positions: number[]) =>
  positions.map((position, index) => ({ id: `t${index + 1}`, position }))

describe('positionBetween', () => {
  it('starts an empty list at one step', () => {
    expect(positionBetween(null, null)).toEqual({ position: STEP, needsRebalance: false })
  })

  it('appends one step after the last item', () => {
    expect(positionBetween(2048, null).position).toBe(2048 + STEP)
  })

  it('prepends halfway between zero and the first item', () => {
    expect(positionBetween(null, 1024).position).toBe(512)
  })

  it('takes the midpoint between two neighbours', () => {
    expect(positionBetween(1024, 2048).position).toBe(1536)
  })

  it('flags a gap smaller than the minimum as needing a rebalance', () => {
    const result = positionBetween(1, 1 + MIN_GAP / 2)
    expect(result.needsRebalance).toBe(true)
    expect(result.position).toBeGreaterThanOrEqual(1)
    expect(result.position).toBeLessThanOrEqual(1 + MIN_GAP / 2)
  })
})

describe('computeMove', () => {
  it('moves an item down within its own list', () => {
    // t1 t2 t3 -> t2 t3 t1 ... dropping t1 at index 1 of [t2, t3] puts it between them.
    const plan = computeMove(items(1024, 2048, 3072), 't1', 1)
    expect(plan).toEqual({ afterId: 't2', beforeId: 't3', position: 2560, needsRebalance: false })
  })

  it('moves an item to the top of its own list', () => {
    const plan = computeMove(items(1024, 2048, 3072), 't3', 0)
    expect(plan).toEqual({ afterId: null, beforeId: 't1', position: 512, needsRebalance: false })
  })

  it('moves an item to the bottom of its own list', () => {
    const plan = computeMove(items(1024, 2048, 3072), 't1', 2)
    expect(plan).toEqual({ afterId: 't3', beforeId: null, position: 4096, needsRebalance: false })
  })

  it('inserts an item coming from another list', () => {
    const plan = computeMove(items(1024, 2048), 'other', 1)
    expect(plan).toEqual({ afterId: 't1', beforeId: 't2', position: 1536, needsRebalance: false })
  })

  it('drops into an empty list', () => {
    expect(computeMove([], 'other', 0)).toEqual({
      afterId: null,
      beforeId: null,
      position: STEP,
      needsRebalance: false,
    })
  })

  it('clamps an out-of-range target index to the ends', () => {
    expect(computeMove(items(1024), 'other', 5).afterId).toBe('t1')
    expect(computeMove(items(1024), 'other', -2).beforeId).toBe('t1')
  })

  it('reports when the neighbours are too close together', () => {
    const plan = computeMove(items(1, 1 + MIN_GAP / 4), 'other', 1)
    expect(plan.needsRebalance).toBe(true)
  })
})

describe('toNeighbourIds', () => {
  const plan = { afterId: 'a', beforeId: 'b', position: 1, needsRebalance: false }

  it('sends both neighbours when the full list is visible', () => {
    expect(toNeighbourIds(plan, { partialView: false })).toEqual({
      after_id: 'a',
      before_id: 'b',
    })
  })

  it('anchors on a single neighbour when the view is filtered', () => {
    // Visible neighbours may not be adjacent in the full list, which the server rejects.
    expect(toNeighbourIds(plan, { partialView: true })).toEqual({ before_id: 'b' })
    expect(toNeighbourIds({ ...plan, beforeId: null }, { partialView: true })).toEqual({
      after_id: 'a',
    })
  })

  it('sends no neighbours for an empty target list', () => {
    const empty = { afterId: null, beforeId: null, position: STEP, needsRebalance: false }
    expect(toNeighbourIds(empty, { partialView: false })).toEqual({})
  })
})
