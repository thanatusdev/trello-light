import type { Announcements, ScreenReaderInstructions } from '@dnd-kit/core'

export const screenReaderInstructions: ScreenReaderInstructions = {
  draggable:
    'To move this item, press Space or Enter. Use the arrow keys to move it, ' +
    'Space or Enter to drop it, or Escape to cancel.',
}

interface Lookup {
  /** Human name for a draggable/droppable id (a task title or "column X"). */
  label: (id: string | number) => string
  /** Where the active item would land if dropped over `overId`, e.g. `position 2 of 3 in "Doing"`. */
  location: (id: string | number, overId: string | number) => string | null
}

/** Live-region messages naming the task and its target column. */
export function makeAnnouncements({ label, location }: Lookup): Announcements {
  const where = (id: string | number, overId: string | number) =>
    location(id, overId) ?? 'its original place'
  return {
    onDragStart: ({ active }) => `Picked up ${label(active.id)}.`,
    onDragOver: ({ active, over }) =>
      over
        ? `${label(active.id)} moved to ${where(active.id, over.id)}.`
        : `${label(active.id)} is no longer over a drop area.`,
    onDragEnd: ({ active, over }) =>
      over
        ? `${label(active.id)} dropped at ${where(active.id, over.id)}.`
        : `${label(active.id)} dropped in its original place.`,
    onDragCancel: ({ active }) => `Moving ${label(active.id)} was cancelled.`,
  }
}
