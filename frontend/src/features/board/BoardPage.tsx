import {
  closestCenter,
  closestCorners,
  type CollisionDetection,
  DndContext,
  type DragEndEvent,
  type DragOverEvent,
  DragOverlay,
  type DragStartEvent,
  getFirstCollision,
  KeyboardSensor,
  PointerSensor,
  pointerWithin,
  TouchSensor,
  type UniqueIdentifier,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import { arrayMove, horizontalListSortingStrategy, SortableContext } from '@dnd-kit/sortable'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { errorMessage } from '@/api/errors'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { countActive } from '@/features/filters/filters'
import { AddColumn } from '@/features/statuses/AddColumn'
import type { Task } from '@/features/tasks/api'
import { useTaskModal } from '@/hooks/use-task-modal'
import { useFiltersStore } from '@/stores/filters-store'

import { type Board, useBoard, useMoveStatus, useMoveTask } from './api'
import { BoardColumn } from './BoardColumn'
import { landingIndex } from './board-state'
import { makeAnnouncements, screenReaderInstructions } from './dnd-announcements'
import { columnDndId, fromDndId, isColumnDndId } from './dnd-ids'
import { boardKeyboardCoordinates } from './dnd-keyboard'
import { TaskCardContent } from './TaskCard'

type ItemsByColumn = Record<string, string[]>

interface DragState {
  type: 'task' | 'column'
  activeId: string
  /** Task ids per column, rearranged live while dragging across columns. */
  items: ItemsByColumn
  columnOrder: string[]
  /**
   * Set on drop: the board the drop was made against. The local order stays on screen
   * until the cache moves on (the optimistic update), so the card never snaps back.
   */
  droppedOn: Board | null
}

/**
 * Tasks: the card under the pointer, else the column under it, else the nearest corner
 * (keyboard drags have no pointer). Columns only ever collide with columns.
 */
const collisionDetection: CollisionDetection = (args) => {
  if (args.active.data.current?.type === 'column') {
    return closestCenter({
      ...args,
      droppableContainers: args.droppableContainers.filter(
        (container) => container.data.current?.type === 'column',
      ),
    })
  }
  const hits = pointerWithin(args)
  const taskHit = hits.find((hit) => !isColumnDndId(hit.id))
  if (taskHit) return [taskHit]
  if (hits.length > 0) return hits
  return closestCorners(args)
}

export function BoardPage() {
  const filters = useFiltersStore((state) => state.filters)
  const clearFilters = useFiltersStore((state) => state.clear)
  const boardQuery = useBoard(filters)
  const moveTask = useMoveTask(filters)
  const moveStatus = useMoveStatus(filters)
  const { openTask, openNew } = useTaskModal()
  const [drag, setDrag] = useState<DragState | null>(null)

  // Moving a card into another column re-lays out both columns under a pointer/keyboard
  // rect that hasn't moved, which can flip the collision straight back to the old column,
  // and so on until React gives up (error #185). Hold the last target until the browser
  // has painted the move (dnd-kit's multiple-containers pattern).
  const lastOverId = useRef<UniqueIdentifier | null>(null)
  const changedColumn = useRef(false)
  const detectCollisions: CollisionDetection = useCallback((args) => {
    if (changedColumn.current && lastOverId.current !== null) return [{ id: lastOverId.current }]
    const collisions = collisionDetection(args)
    lastOverId.current = getFirstCollision(collisions, 'id')
    return collisions
  }, [])
  const liveItems = drag?.items
  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      changedColumn.current = false
    })
    return () => {
      cancelAnimationFrame(frame)
    }
  }, [liveItems])

  const sensors = useSensors(
    // A short distance keeps plain clicks opening the task instead of starting a drag.
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    // Press-and-hold on touch, so swiping still scrolls the board horizontally.
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: boardKeyboardCoordinates }),
  )

  const board = boardQuery.data
  const statusFilter = filters.status_id
  const visibleColumns = useMemo(
    () => board?.columns.filter((c) => !statusFilter || c.id === statusFilter) ?? [],
    [board, statusFilter],
  )
  const tasksById = useMemo(
    () => new Map(visibleColumns.flatMap((c) => c.tasks.map((t) => [t.id, t] as const))),
    [visibleColumns],
  )
  const columnsById = useMemo(() => new Map(visibleColumns.map((c) => [c.id, c])), [visibleColumns])

  const liveDrag = drag && (drag.droppedOn === null || drag.droppedOn === board) ? drag : null
  const items: ItemsByColumn =
    liveDrag?.items ??
    Object.fromEntries(visibleColumns.map((c) => [c.id, c.tasks.map((t) => t.id)]))
  const columnOrder = liveDrag?.columnOrder ?? visibleColumns.map((c) => c.id)

  const announcements = makeAnnouncements({
    label: (id) =>
      isColumnDndId(id)
        ? `column “${columnsById.get(fromDndId(id))?.name ?? ''}”`
        : `task “${tasksById.get(String(id))?.title ?? ''}”`,
    // The drop lands where the item is over (see handleDragEnd), so announce that slot:
    // within a column the list isn't rearranged until the drop.
    location: (id, overId) => {
      if (isColumnDndId(id)) {
        if (!columnOrder.includes(fromDndId(id))) return null
        const index = landingIndex(columnOrder, fromDndId(id), fromDndId(overId))
        return `position ${index + 1} of ${columnOrder.length}`
      }
      for (const [columnId, ids] of Object.entries(items)) {
        if (ids.includes(String(id))) {
          const index = landingIndex(ids, String(id), String(overId))
          const name = columnsById.get(columnId)?.name ?? ''
          return `position ${index + 1} of ${ids.length} in “${name}”`
        }
      }
      return null
    },
  })

  if (boardQuery.isPending) return <BoardSkeleton />
  if (boardQuery.isError) {
    return (
      <div className="flex flex-col items-start gap-3 p-4">
        <p className="text-destructive">
          Couldn’t load the board. {errorMessage(boardQuery.error)}
        </p>
        <Button variant="outline" onClick={() => void boardQuery.refetch()}>
          Try again
        </Button>
      </div>
    )
  }

  const filtered = countActive({ ...filters, status_id: undefined }) > 0
  const noMatches = filtered && visibleColumns.every((c) => c.tasks.length === 0)
  const findColumn = (id: string, byColumn: ItemsByColumn) =>
    byColumn[id] ? id : Object.keys(byColumn).find((columnId) => byColumn[columnId]?.includes(id))

  function handleDragStart({ active }: DragStartEvent) {
    lastOverId.current = null
    changedColumn.current = false
    const type = active.data.current?.type === 'column' ? 'column' : 'task'
    setDrag({ type, activeId: fromDndId(active.id), items, columnOrder, droppedOn: null })
  }

  function handleDragOver({ active, over }: DragOverEvent) {
    if (!over) return
    const activeId = String(active.id)
    const overId = String(over.id)
    const translated = active.rect.current.translated
    const below = translated ? translated.top > over.rect.top + over.rect.height / 2 : false

    // Functional update: several drag-over events can fire before React re-renders.
    setDrag((current) => {
      if (current?.type !== 'task') return current
      const from = findColumn(activeId, current.items)
      const to = findColumn(fromDndId(overId), current.items)
      if (!from || !to || from === to) return current

      changedColumn.current = true
      const target = current.items[to] ?? []
      const overIndex = target.indexOf(overId)
      const index = overIndex === -1 ? target.length : overIndex + (below ? 1 : 0)
      return {
        ...current,
        items: {
          ...current.items,
          [from]: (current.items[from] ?? []).filter((id) => id !== activeId),
          [to]: [...target.slice(0, index), activeId, ...target.slice(index)],
        },
      }
    })
  }

  function handleDragEnd({ active, over }: DragEndEvent) {
    if (!drag || !over) {
      setDrag(null)
      return
    }
    if (drag.type === 'column') {
      const order = arrayMove(
        drag.columnOrder,
        drag.columnOrder.indexOf(drag.activeId),
        drag.columnOrder.indexOf(fromDndId(over.id)),
      )
      const moved = moveStatus.move(drag.activeId, order.indexOf(drag.activeId))
      setDrag(moved ? { ...drag, columnOrder: order, droppedOn: board ?? null } : null)
      return
    }

    const columnId = findColumn(String(active.id), drag.items)
    if (!columnId) {
      setDrag(null)
      return
    }
    let list = drag.items[columnId] ?? []
    list = arrayMove(
      list,
      list.indexOf(drag.activeId),
      landingIndex(list, drag.activeId, String(over.id)),
    )
    const moved = moveTask.move(drag.activeId, columnId, list.indexOf(drag.activeId))
    setDrag(
      moved
        ? { ...drag, items: { ...drag.items, [columnId]: list }, droppedOn: board ?? null }
        : null,
    )
  }

  function moveColumnBy(columnId: string, direction: -1 | 1) {
    const index = columnOrder.indexOf(columnId)
    moveStatus.move(columnId, index + direction)
  }

  const activeTask =
    liveDrag?.type === 'task' && !liveDrag.droppedOn ? tasksById.get(liveDrag.activeId) : undefined
  const activeColumn =
    liveDrag?.type === 'column' && !liveDrag.droppedOn
      ? columnsById.get(liveDrag.activeId)
      : undefined

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      {noMatches && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border bg-muted/40 px-3 py-2 text-sm">
          <span>No tasks match these filters.</span>
          <Button variant="outline" size="sm" onClick={clearFilters}>
            Clear filters
          </Button>
        </div>
      )}
      {visibleColumns.length === 0 && !statusFilter && (
        <div className="rounded-lg border border-dashed p-6 text-center text-muted-foreground">
          <p className="font-medium text-foreground">Your board has no columns yet.</p>
          <p className="text-sm">Add a column to start organising tasks.</p>
        </div>
      )}
      <DndContext
        sensors={sensors}
        collisionDetection={detectCollisions}
        accessibility={{ announcements, screenReaderInstructions }}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragEnd={handleDragEnd}
        onDragCancel={() => {
          setDrag(null)
        }}
      >
        <div
          role="region"
          aria-label="Board"
          // `relative` contains absolutely positioned descendants (sr-only text in column
          // headers); without it they escape the scroll clip and widen the page on phones.
          className="relative -mx-4 flex min-h-0 flex-1 snap-x snap-mandatory items-start gap-3 overflow-x-auto px-4 pb-4 sm:snap-none"
        >
          <SortableContext
            items={columnOrder.map(columnDndId)}
            strategy={horizontalListSortingStrategy}
          >
            {columnOrder.map((columnId, index) => {
              const column = columnsById.get(columnId)
              if (!column) return null
              const tasks = (items[columnId] ?? [])
                .map((id) => tasksById.get(id))
                .filter((t): t is Task => t !== undefined)
              return (
                <BoardColumn
                  key={columnId}
                  column={column}
                  tasks={tasks}
                  filtered={filtered}
                  reorderDisabled={Boolean(statusFilter)}
                  isFirst={index === 0}
                  isLast={index === columnOrder.length - 1}
                  onMove={(direction) => {
                    moveColumnBy(columnId, direction)
                  }}
                  onOpenTask={openTask}
                  onAddTask={() => {
                    openNew(columnId)
                  }}
                />
              )
            })}
          </SortableContext>
          {!statusFilter && <AddColumn />}
        </div>
        <DragOverlay>
          {activeTask && (
            <div className="w-68 rotate-2 rounded-lg border bg-card p-3 shadow-lg">
              <TaskCardContent task={activeTask} />
            </div>
          )}
          {activeColumn && (
            <div className="w-72 rounded-xl border bg-muted p-3 text-sm font-semibold shadow-lg">
              {activeColumn.name}
            </div>
          )}
        </DragOverlay>
      </DndContext>
    </div>
  )
}

function BoardSkeleton() {
  return (
    <div role="status" aria-label="Loading board" className="flex gap-3 overflow-hidden">
      {[4, 2, 3].map((count, column) => (
        <div
          key={column}
          className="flex w-72 shrink-0 flex-col gap-2 rounded-xl border bg-muted/50 p-2"
        >
          <Skeleton className="h-6 w-1/2" />
          {Array.from({ length: count }, (_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      ))}
    </div>
  )
}
