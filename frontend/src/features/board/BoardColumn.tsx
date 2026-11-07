import { SortableContext, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  CheckCircle2Icon,
  GripVerticalIcon,
  MoreHorizontalIcon,
  PencilIcon,
  PlusIcon,
  Trash2Icon,
} from 'lucide-react'
import { useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { ColumnTitle } from '@/features/statuses/ColumnTitle'
import { DeleteColumnDialog } from '@/features/statuses/DeleteColumnDialog'
import type { Task } from '@/features/tasks/api'
import { cn } from '@/lib/utils'

import type { ColumnSummary } from './api'
import { columnDndId } from './dnd-ids'
import { SortableTaskCard } from './TaskCard'

interface BoardColumnProps {
  column: ColumnSummary
  tasks: Task[]
  /** Board filters are hiding some tasks. */
  filtered: boolean
  /** Column reordering is off, e.g. while a status filter hides other columns. */
  reorderDisabled: boolean
  isFirst: boolean
  isLast: boolean
  onMove: (direction: -1 | 1) => void
  onOpenTask: (taskId: string) => void
  onAddTask: () => void
}

export function BoardColumn({
  column,
  tasks,
  filtered,
  reorderDisabled,
  isFirst,
  isLast,
  onMove,
  onOpenTask,
  onAddTask,
}: BoardColumnProps) {
  const [renaming, setRenaming] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const {
    setNodeRef,
    setActivatorNodeRef,
    listeners,
    attributes,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: columnDndId(column.id),
    data: { type: 'column', columnId: column.id },
    disabled: { draggable: reorderDisabled, droppable: false },
  })

  return (
    <section
      ref={setNodeRef}
      aria-label={column.name}
      style={{ transform: CSS.Translate.toString(transform), transition }}
      className={cn(
        'flex max-h-full w-72 shrink-0 snap-start flex-col rounded-xl border bg-muted/50',
        isDragging && 'opacity-40',
      )}
    >
      <header className="flex items-center gap-1 p-2">
        {!reorderDisabled && (
          <button
            ref={setActivatorNodeRef}
            type="button"
            {...attributes}
            {...listeners}
            aria-label={`Move column ${column.name}`}
            className="cursor-grab rounded p-0.5 text-muted-foreground hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none active:cursor-grabbing"
          >
            <GripVerticalIcon aria-hidden className="size-4" />
          </button>
        )}
        <ColumnTitle
          id={column.id}
          name={column.name}
          editing={renaming}
          onEditingChange={setRenaming}
        />
        {column.is_done && (
          <Badge variant="secondary" className="gap-1" title="Tasks here are marked complete">
            <CheckCircle2Icon aria-hidden />
            Done
          </Badge>
        )}
        <span className="px-1 text-xs text-muted-foreground tabular-nums">
          <span className="sr-only">Tasks: </span>
          {tasks.length}
        </span>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon-sm" aria-label={`${column.name} column actions`}>
              <MoreHorizontalIcon aria-hidden />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem
              onSelect={() => {
                setRenaming(true)
              }}
            >
              <PencilIcon aria-hidden />
              Rename
            </DropdownMenuItem>
            <DropdownMenuItem
              disabled={reorderDisabled || isFirst}
              onSelect={() => {
                onMove(-1)
              }}
            >
              <ArrowLeftIcon aria-hidden />
              Move left
            </DropdownMenuItem>
            <DropdownMenuItem
              disabled={reorderDisabled || isLast}
              onSelect={() => {
                onMove(1)
              }}
            >
              <ArrowRightIcon aria-hidden />
              Move right
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              variant="destructive"
              onSelect={() => {
                setDeleting(true)
              }}
            >
              <Trash2Icon aria-hidden />
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </header>

      <SortableContext items={tasks.map((t) => t.id)} strategy={verticalListSortingStrategy}>
        <ul className="flex min-h-16 flex-1 flex-col gap-2 overflow-y-auto px-2 pb-1">
          {tasks.map((task) => (
            <SortableTaskCard key={task.id} task={task} columnId={column.id} onOpen={onOpenTask} />
          ))}
          {tasks.length === 0 && (
            <li className="flex flex-1 items-center justify-center rounded-lg border border-dashed p-4 text-center text-xs text-muted-foreground">
              {filtered ? 'No matching tasks' : 'No tasks yet'}
            </li>
          )}
        </ul>
      </SortableContext>

      <div className="p-2">
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start text-muted-foreground"
          aria-label={`Add task to ${column.name}`}
          onClick={onAddTask}
        >
          <PlusIcon aria-hidden />
          Add task
        </Button>
      </div>

      <DeleteColumnDialog
        id={column.id}
        name={column.name}
        open={deleting}
        onOpenChange={setDeleting}
      />
    </section>
  )
}
