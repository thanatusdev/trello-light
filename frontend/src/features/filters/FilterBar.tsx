import { SearchIcon, XIcon } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useColumns } from '@/features/board/api'
import { AssigneeCombobox } from '@/features/tasks/AssigneeCombobox'
import { DueDatePicker } from '@/features/tasks/DueDatePicker'
import { useFiltersStore } from '@/stores/filters-store'

import { countActive } from './filters'

const ALL = 'all'
const SEARCH_DEBOUNCE_MS = 300

export function FilterBar() {
  const filters = useFiltersStore((state) => state.filters)
  const setFilter = useFiltersStore((state) => state.setFilter)
  const clear = useFiltersStore((state) => state.clear)
  const { data: columns = [] } = useColumns()
  const active = countActive(filters)
  const setSearch = useCallback(
    (value: string) => {
      setFilter('search', value || undefined)
    },
    [setFilter],
  )

  return (
    <search aria-label="Filter tasks" className="flex flex-wrap items-end gap-2">
      <SearchInput value={filters.search ?? ''} onChange={setSearch} />

      <div className="flex w-full flex-col gap-1 sm:w-40">
        <Label htmlFor="filter-status" className="text-xs text-muted-foreground">
          Column
        </Label>
        <Select
          value={filters.status_id ?? ALL}
          onValueChange={(value) => {
            setFilter('status_id', value === ALL ? undefined : value)
          }}
        >
          <SelectTrigger id="filter-status" className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All columns</SelectItem>
            {columns.map((column) => (
              <SelectItem key={column.id} value={column.id}>
                {column.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="flex w-full flex-col gap-1 sm:w-44">
        <Label htmlFor="filter-assignee" className="text-xs text-muted-foreground">
          Assignee
        </Label>
        <AssigneeCombobox
          id="filter-assignee"
          emptyLabel="Anyone"
          value={filters.assignee_id ?? null}
          onChange={(value) => {
            setFilter('assignee_id', value ?? undefined)
          }}
        />
      </div>

      <div className="flex w-full flex-col gap-1 sm:w-36">
        <Label htmlFor="filter-completed" className="text-xs text-muted-foreground">
          Progress
        </Label>
        <Select
          value={filters.is_completed === undefined ? ALL : String(filters.is_completed)}
          onValueChange={(value) => {
            setFilter('is_completed', value === ALL ? undefined : value === 'true')
          }}
        >
          <SelectTrigger id="filter-completed" className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All tasks</SelectItem>
            <SelectItem value="false">Open</SelectItem>
            <SelectItem value="true">Completed</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <fieldset className="flex w-full flex-col gap-1 sm:w-auto">
        <legend className="mb-1 text-xs text-muted-foreground">Due between</legend>
        <div className="flex items-center gap-1">
          <DueDatePicker
            aria-label="due from"
            placeholder="From"
            className="min-w-0 flex-1 sm:w-40"
            value={filters.due_after ?? null}
            // The API rejects a range that ends before it starts.
            isDisabled={(date) => filters.due_before !== undefined && date > filters.due_before}
            onChange={(value) => {
              setFilter('due_after', value ?? undefined)
            }}
          />
          <DueDatePicker
            aria-label="due until"
            placeholder="Until"
            className="min-w-0 flex-1 sm:w-40"
            value={filters.due_before ?? null}
            isDisabled={(date) => filters.due_after !== undefined && date < filters.due_after}
            onChange={(value) => {
              setFilter('due_before', value ?? undefined)
            }}
          />
        </div>
      </fieldset>

      {active > 0 && (
        <Button variant="ghost" onClick={clear}>
          <XIcon aria-hidden />
          Clear filters ({active})
        </Button>
      )}
    </search>
  )
}

/** Search box that only updates the filter once typing pauses. */
function SearchInput({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const [text, setText] = useState(value)
  const [lastValue, setLastValue] = useState(value)

  // Follow outside changes (Clear filters, back/forward) without clobbering typing.
  if (value !== lastValue) {
    setLastValue(value)
    if (value !== text.trim()) setText(value)
  }

  useEffect(() => {
    const trimmed = text.trim()
    if (trimmed === value) return
    const timer = setTimeout(() => {
      onChange(trimmed)
    }, SEARCH_DEBOUNCE_MS)
    return () => {
      clearTimeout(timer)
    }
  }, [text, value, onChange])

  return (
    <div className="flex w-full flex-col gap-1 sm:w-56">
      <Label htmlFor="filter-search" className="text-xs text-muted-foreground">
        Search
      </Label>
      <div className="relative">
        <SearchIcon
          aria-hidden
          className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
        />
        <Input
          id="filter-search"
          type="search"
          placeholder="Search titles…"
          maxLength={200}
          className="pl-8"
          value={text}
          onChange={(event) => {
            setText(event.target.value)
          }}
        />
      </div>
    </div>
  )
}
