import type { ClientRect, KeyboardCoordinateGetter } from '@dnd-kit/core'
import { sortableKeyboardCoordinates } from '@dnd-kit/sortable'

/** Is `rect` wholly past the middle of the dragged card, in the arrow's direction? */
function isBeyond(code: string, dragged: ClientRect, rect: ClientRect) {
  const middle = dragged.left + dragged.width / 2
  return code === 'ArrowRight' ? rect.left > middle : rect.right < middle
}

/**
 * `sortableKeyboardCoordinates`, but Left/Right only consider other columns. The stock getter
 * counts anything whose left edge is even a subpixel further right as "to the right", so the
 * first ArrowRight could move a card down its own column instead of to the next one.
 */
export const boardKeyboardCoordinates: KeyboardCoordinateGetter = (event, args) => {
  const { collisionRect, droppableRects, droppableContainers } = args.context
  const horizontal = event.code === 'ArrowLeft' || event.code === 'ArrowRight'
  if (!horizontal || !collisionRect) return sortableKeyboardCoordinates(event, args)

  // The stock getter only reads `getEnabled()` and `get()` from the container map.
  const inOtherColumns = {
    getEnabled: () =>
      droppableContainers.getEnabled().filter((container) => {
        const rect = droppableRects.get(container.id)
        return rect !== undefined && isBeyond(event.code, collisionRect, rect)
      }),
    get: (id: Parameters<typeof droppableContainers.get>[0]) => droppableContainers.get(id),
  } as unknown as typeof droppableContainers
  return sortableKeyboardCoordinates(event, {
    ...args,
    context: { ...args.context, droppableContainers: inOtherColumns },
  })
}
