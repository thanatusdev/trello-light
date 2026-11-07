import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { format, parseISO } from 'date-fns'
import { CalendarIcon, CheckCircle2Icon, GripVerticalIcon } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import type { Task } from '@/features/tasks/api'
import { utcToday } from '@/features/tasks/schema'
import { cn } from '@/lib/utils'

function initials(name: string) {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
}

/** The visible card; shared by the sortable card and the drag overlay. */
export function TaskCardContent({ task }: { task: Task }) {
  const completed = task.completed_at !== null
  const overdue = !completed && task.due_date !== null && task.due_date < utcToday()

  return (
    <div className="flex min-w-0 flex-1 flex-col gap-2">
      <span
        className={cn(
          'text-sm font-medium break-words',
          completed && 'text-muted-foreground line-through',
        )}
      >
        {task.title}
      </span>
      {(task.due_date !== null || task.assignee !== null || completed) && (
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          {completed && (
            <Badge variant="secondary" className="gap-1">
              <CheckCircle2Icon aria-hidden />
              Done
            </Badge>
          )}
          {task.due_date && (
            <Badge variant={overdue ? 'destructive' : 'outline'} className="gap-1">
              <CalendarIcon aria-hidden />
              <span className="sr-only">{overdue ? 'Overdue, due' : 'Due'}</span>
              {format(parseISO(task.due_date), 'MMM d')}
            </Badge>
          )}
          {task.assignee && (
            <span
              title={task.assignee.full_name}
              className="ml-auto flex size-6 items-center justify-center rounded-full bg-muted text-[0.65rem] font-semibold"
            >
              <span aria-hidden>{initials(task.assignee.full_name)}</span>
              <span className="sr-only">Assigned to {task.assignee.full_name}</span>
            </span>
          )}
        </div>
      )}
    </div>
  )
}

interface SortableTaskCardProps {
  task: Task
  columnId: string
  onOpen: (taskId: string) => void
}

/**
 * A draggable card. Pointer and touch drags start anywhere on the card; keyboard drags
 * start from the grip button (Space/Enter), so Enter on the title still opens the task.
 */
export function SortableTaskCard({ task, columnId, onOpen }: SortableTaskCardProps) {
  const {
    setNodeRef,
    setActivatorNodeRef,
    listeners,
    attributes,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: task.id, data: { type: 'task', columnId } })
  const { onKeyDown, ...pointerListeners } = listeners ?? {}

  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Translate.toString(transform), transition }}
      className={cn(
        'relative flex items-start gap-1 rounded-lg border bg-card p-3 shadow-xs transition-shadow hover:shadow-sm',
        isDragging && 'opacity-40',
      )}
      {...pointerListeners}
    >
      <TaskCardContent task={task} />
      {/* Stretched over the whole card so a click anywhere opens the task. */}
      <button
        type="button"
        className="absolute inset-0 rounded-lg focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
        onClick={() => {
          onOpen(task.id)
        }}
      >
        <span className="sr-only">Open {task.title}</span>
      </button>
      <button
        ref={setActivatorNodeRef}
        type="button"
        {...attributes}
        onKeyDown={onKeyDown as React.KeyboardEventHandler | undefined}
        aria-label={`Move ${task.title}`}
        className="relative z-10 -mr-1 cursor-grab rounded p-0.5 text-muted-foreground hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none active:cursor-grabbing"
      >
        <GripVerticalIcon aria-hidden className="size-4" />
      </button>
    </li>
  )
}
