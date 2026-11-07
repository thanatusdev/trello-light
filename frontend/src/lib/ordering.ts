/**
 * Fractional indexing, mirroring the backend's `app/domain/ordering.py`.
 *
 * The server owns the real positions (it computes them from the neighbour ids we send
 * and rebalances a list when gaps get too small). The client computes the same midpoint
 * so an optimistic move lands where the server will put it.
 */

export const STEP = 1024
export const MIN_GAP = 1e-6

export interface Positioned {
  id: string
  position: number
}

export interface MovePlan {
  /** Item that ends up directly before the moved one, if any. */
  afterId: string | null
  /** Item that ends up directly after the moved one, if any. */
  beforeId: string | null
  position: number
  /** The gap was too small; the server will renumber the list. */
  needsRebalance: boolean
}

export function positionBetween(
  prev: number | null,
  next: number | null,
): { position: number; needsRebalance: boolean } {
  if (next === null) return { position: prev === null ? STEP : prev + STEP, needsRebalance: false }
  const lower = prev ?? 0
  const gap = next - lower
  return { position: lower + gap / 2, needsRebalance: gap < MIN_GAP }
}

/**
 * Where `activeId` lands when dropped at `targetIndex` of `items` (the target list in its
 * current order). `items` may include the active item itself (a move within one list);
 * `targetIndex` is counted with the active item removed.
 */
export function computeMove(
  items: readonly Positioned[],
  activeId: string,
  targetIndex: number,
): MovePlan {
  const others = items.filter((item) => item.id !== activeId)
  const index = Math.min(Math.max(targetIndex, 0), others.length)
  const after = others[index - 1] ?? null
  const before = others[index] ?? null
  return {
    afterId: after?.id ?? null,
    beforeId: before?.id ?? null,
    ...positionBetween(after?.position ?? null, before?.position ?? null),
  }
}

/**
 * The neighbour ids to send to a `/move` endpoint. When only part of the list is visible
 * (filters active) the visible neighbours may not be adjacent server-side, which it
 * rejects as stale, so anchor on a single neighbour instead.
 */
export function toNeighbourIds(
  plan: MovePlan,
  { partialView }: { partialView: boolean },
): { after_id?: string; before_id?: string } {
  if (partialView) {
    if (plan.beforeId) return { before_id: plan.beforeId }
    if (plan.afterId) return { after_id: plan.afterId }
    return {}
  }
  return {
    ...(plan.afterId ? { after_id: plan.afterId } : {}),
    ...(plan.beforeId ? { before_id: plan.beforeId } : {}),
  }
}
