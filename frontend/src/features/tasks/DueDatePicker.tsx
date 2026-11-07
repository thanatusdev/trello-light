import { format, parseISO } from 'date-fns'
import { CalendarIcon, XIcon } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Calendar } from '@/components/ui/calendar'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { cn } from '@/lib/utils'

interface DueDatePickerProps {
  id?: string
  /** `YYYY-MM-DD` or null. */
  value: string | null
  onChange: (value: string | null) => void
  placeholder?: string
  /** Days that may not be picked, as `YYYY-MM-DD`. */
  isDisabled?: (date: string) => boolean
  invalid?: boolean
  className?: string
  'aria-label'?: string
}

const toIso = (date: Date) => format(date, 'yyyy-MM-dd')

/** Date-only picker; values are plain ISO dates with no time zone. */
export function DueDatePicker({
  id,
  value,
  onChange,
  placeholder = 'Pick a date',
  isDisabled,
  invalid,
  className,
  'aria-label': ariaLabel,
}: DueDatePickerProps) {
  const [open, setOpen] = useState(false)
  const selected = value ? parseISO(value) : undefined

  return (
    <div className={cn('flex items-center gap-1', className)}>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            id={id}
            type="button"
            variant="outline"
            aria-label={ariaLabel}
            aria-invalid={invalid ? true : undefined}
            className={cn('flex-1 justify-start font-normal', !value && 'text-muted-foreground')}
          >
            <CalendarIcon aria-hidden />
            {selected ? format(selected, 'PP') : placeholder}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-auto p-0" align="start">
          <Calendar
            mode="single"
            selected={selected}
            defaultMonth={selected}
            disabled={isDisabled ? (date) => isDisabled(toIso(date)) : undefined}
            onSelect={(date) => {
              onChange(date ? toIso(date) : null)
              setOpen(false)
            }}
          />
        </PopoverContent>
      </Popover>
      {value && (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label={`Clear ${ariaLabel ?? 'date'}`}
          onClick={() => {
            onChange(null)
          }}
        >
          <XIcon aria-hidden />
        </Button>
      )}
    </div>
  )
}
