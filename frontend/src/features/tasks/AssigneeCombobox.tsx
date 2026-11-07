import { ChevronsUpDownIcon } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { cn } from '@/lib/utils'

import { useUsers } from './users'

interface AssigneeComboboxProps {
  id?: string
  value: string | null
  onChange: (value: string | null) => void
  /** Shown while users load, e.g. the task's current assignee. */
  fallbackName?: string | null
  /** Label for the "no assignee" option. */
  emptyLabel?: string
}

/** Searchable picker over active users, with an "Unassigned" option. */
export function AssigneeCombobox({
  id,
  value,
  onChange,
  fallbackName,
  emptyLabel = 'Unassigned',
}: AssigneeComboboxProps) {
  const [open, setOpen] = useState(false)
  const { data: users = [], isPending, isError, refetch, isRefetching } = useUsers()
  const selected = users.find((user) => user.id === value)
  const label = selected?.full_name ?? (value ? fallbackName : null) ?? emptyLabel

  function choose(next: string | null) {
    onChange(next)
    setOpen(false)
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className={cn('w-full justify-between font-normal', !value && 'text-muted-foreground')}
        >
          <span className="truncate">{label}</span>
          <ChevronsUpDownIcon aria-hidden className="opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-(--radix-popover-trigger-width) min-w-56 p-0" align="start">
        <Command>
          <CommandInput placeholder="Search people…" />
          <CommandList>
            {isError ? (
              // Distinct from "No one matches.": the list is unknown, not empty.
              <div role="alert" className="flex items-center justify-between gap-2 p-3 text-sm">
                <span className="text-destructive">Couldn&apos;t load people.</span>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={isRefetching}
                  onClick={() => void refetch()}
                >
                  Try again
                </Button>
              </div>
            ) : (
              <CommandEmpty>{isPending ? 'Loading…' : 'No one matches.'}</CommandEmpty>
            )}
            <CommandGroup>
              <CommandItem
                value={`__none__ ${emptyLabel}`}
                data-checked={value === null}
                onSelect={() => {
                  choose(null)
                }}
              >
                {emptyLabel}
              </CommandItem>
              {users.map((user) => (
                <CommandItem
                  key={user.id}
                  value={`${user.full_name} ${user.email} ${user.id}`}
                  data-checked={value === user.id}
                  onSelect={() => {
                    choose(user.id)
                  }}
                >
                  <span className="truncate">{user.full_name}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
