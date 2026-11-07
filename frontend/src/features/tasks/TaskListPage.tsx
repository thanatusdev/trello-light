import { format, parseISO } from 'date-fns'
import { ChevronLeftIcon, ChevronRightIcon } from 'lucide-react'
import { useSearchParams } from 'react-router'

import { errorMessage } from '@/api/errors'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useColumns } from '@/features/board/api'
import { countActive } from '@/features/filters/filters'
import { useTaskModal } from '@/hooks/use-task-modal'
import { useFiltersStore } from '@/stores/filters-store'

import { type Task, useTasks } from './api'
import { PAGE_SIZES, parsePaging } from './paging'

const formatDate = (iso: string | null) => (iso ? format(parseISO(iso), 'PP') : '—')

export function TaskListPage() {
  const filters = useFiltersStore((state) => state.filters)
  const clearFilters = useFiltersStore((state) => state.clear)
  const [searchParams, setSearchParams] = useSearchParams()
  const { page, size } = parsePaging(searchParams)
  const tasksQuery = useTasks({ filters, page, size })
  const { data: columns = [] } = useColumns()
  const { openTask } = useTaskModal()
  const statusName = (id: string) => columns.find((c) => c.id === id)?.name ?? '—'

  function setPaging(next: { page?: number; size?: number }) {
    setSearchParams((previous) => {
      const params = new URLSearchParams(previous)
      if (next.page !== undefined) params.set('page', String(next.page))
      if (next.size !== undefined) {
        params.set('size', String(next.size))
        params.delete('page')
      }
      return params
    })
  }

  if (tasksQuery.isPending) {
    return (
      <div role="status" aria-label="Loading tasks" className="flex flex-col gap-2">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    )
  }
  if (tasksQuery.isError) {
    return (
      <div className="flex flex-col items-start gap-3">
        <p className="text-destructive">Couldn’t load tasks. {errorMessage(tasksQuery.error)}</p>
        <Button variant="outline" onClick={() => void tasksQuery.refetch()}>
          Try again
        </Button>
      </div>
    )
  }

  const { items, total, pages } = tasksQuery.data

  if (items.length === 0) {
    const filtered = countActive(filters) > 0
    return (
      <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed p-8 text-center">
        <p className="font-medium">
          {page > 1 && total > 0
            ? 'This page is empty.'
            : filtered
              ? 'No tasks match these filters.'
              : 'No tasks yet.'}
        </p>
        {page > 1 && total > 0 ? (
          <Button
            variant="outline"
            onClick={() => {
              setPaging({ page: 1 })
            }}
          >
            Go to the first page
          </Button>
        ) : (
          filtered && (
            <Button variant="outline" onClick={clearFilters}>
              Clear filters
            </Button>
          )
        )}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Wide screens: a table. */}
      <div className="hidden rounded-lg border sm:block">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Title</TableHead>
              <TableHead>Column</TableHead>
              <TableHead>Assignee</TableHead>
              <TableHead>Due</TableHead>
              <TableHead>Completed</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((task) => (
              <TableRow
                key={task.id}
                className="cursor-pointer"
                onClick={() => {
                  openTask(task.id)
                }}
              >
                <TableCell className="max-w-80 font-medium">
                  <button
                    type="button"
                    className="max-w-full truncate text-left hover:underline focus-visible:underline focus-visible:outline-none"
                    onClick={(event) => {
                      event.stopPropagation()
                      openTask(task.id)
                    }}
                  >
                    {task.title}
                  </button>
                </TableCell>
                <TableCell>{statusName(task.status_id)}</TableCell>
                <TableCell>{task.assignee?.full_name ?? '—'}</TableCell>
                <TableCell>{formatDate(task.due_date)}</TableCell>
                <TableCell>{formatDate(task.completed_at)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Phones: stacked cards. */}
      <ul className="flex flex-col gap-2 sm:hidden">
        {items.map((task) => (
          <li key={task.id}>
            <TaskListCard
              task={task}
              statusName={statusName(task.status_id)}
              onOpen={() => {
                openTask(task.id)
              }}
            />
          </li>
        ))}
      </ul>

      <nav
        aria-label="Pagination"
        className="flex flex-wrap items-center justify-between gap-3 text-sm"
      >
        <div className="flex items-center gap-2">
          <Label htmlFor="page-size" className="text-muted-foreground">
            Per page
          </Label>
          <Select
            value={String(size)}
            onValueChange={(value) => {
              setPaging({ size: Number(value) })
            }}
          >
            <SelectTrigger id="page-size" size="sm" className="w-20">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PAGE_SIZES.map((option) => (
                <SelectItem key={option} value={String(option)}>
                  {option}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground" aria-live="polite">
            Page {page} of {Math.max(pages, 1)} · {total} {total === 1 ? 'task' : 'tasks'}
          </span>
          <Button
            variant="outline"
            size="icon-sm"
            aria-label="Previous page"
            disabled={page <= 1}
            onClick={() => {
              setPaging({ page: page - 1 })
            }}
          >
            <ChevronLeftIcon aria-hidden />
          </Button>
          <Button
            variant="outline"
            size="icon-sm"
            aria-label="Next page"
            disabled={page >= pages}
            onClick={() => {
              setPaging({ page: page + 1 })
            }}
          >
            <ChevronRightIcon aria-hidden />
          </Button>
        </div>
      </nav>
    </div>
  )
}

function TaskListCard({
  task,
  statusName,
  onOpen,
}: {
  task: Task
  statusName: string
  onOpen: () => void
}) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className="flex w-full flex-col gap-1.5 rounded-lg border bg-card p-3 text-left focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
    >
      <span className="font-medium break-words">{task.title}</span>
      <span className="flex flex-wrap gap-1.5 text-xs text-muted-foreground">
        <Badge variant="outline">{statusName}</Badge>
        {task.assignee && <span>{task.assignee.full_name}</span>}
        {task.due_date && <span>Due {formatDate(task.due_date)}</span>}
        {task.completed_at && <span>Completed {formatDate(task.completed_at)}</span>}
      </span>
    </button>
  )
}
