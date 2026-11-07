import type { ClientRect, DroppableContainer, KeyboardCoordinateGetter } from '@dnd-kit/core'

import { boardKeyboardCoordinates } from './dnd-keyboard'

type Args = Parameters<KeyboardCoordinateGetter>[1]

const CARD = { width: 286, height: 70 }

function rect(left: number, top: number): ClientRect {
  return { ...CARD, left, top, right: left + CARD.width, bottom: top + CARD.height }
}

class Containers extends Map<string, DroppableContainer> {
  getEnabled() {
    return [...this.values()].filter((c) => !c.disabled)
  }
}

function container(id: string, containerId: string, index: number, items: string[]) {
  const node = document.createElement('li')
  document.body.append(node)
  return {
    id,
    key: id,
    disabled: false,
    node: { current: node },
    rect: { current: null },
    data: { current: { sortable: { containerId, index, items } } },
  } as unknown as DroppableContainer
}

/**
 * Card A tops column 1, card B sits below it (a subpixel further right, as real layouts
 * produce), card C tops column 2. A is being dragged with the keyboard.
 */
function context(): Args {
  const rects = new Map<string, ClientRect>([
    ['A', rect(25, 186)],
    ['B', rect(25.4, 272)],
    ['C', rect(325, 186)],
  ])
  const containers = new Containers([
    ['A', container('A', 'col-1', 0, ['A', 'B'])],
    ['B', container('B', 'col-1', 1, ['A', 'B'])],
    ['C', container('C', 'col-2', 0, ['C'])],
  ])
  return {
    active: 'A',
    currentCoordinates: { x: 25, y: 186 },
    context: {
      active: { id: 'A' },
      collisionRect: rect(25, 186),
      droppableRects: rects,
      droppableContainers: containers,
      over: { id: 'A' },
      scrollableAncestors: [],
    },
  } as unknown as Args
}

const key = (code: string) => new KeyboardEvent('keydown', { code })

describe('boardKeyboardCoordinates', () => {
  it('moves right to the next column, not to a card below in the same column', () => {
    expect(boardKeyboardCoordinates(key('ArrowRight'), context())).toEqual({ x: 325, y: 186 })
  })

  it('does not move left from the first column', () => {
    expect(boardKeyboardCoordinates(key('ArrowLeft'), context())).toBeUndefined()
  })

  it('still moves vertically within a column', () => {
    expect(boardKeyboardCoordinates(key('ArrowDown'), context())).toEqual({ x: 25.4, y: 272 })
  })
})
