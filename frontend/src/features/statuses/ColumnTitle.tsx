import { useState } from 'react'

import { errorMessage } from '@/api/errors'
import { Input } from '@/components/ui/input'

import { useRenameStatus, validateStatusName } from './api'

interface ColumnTitleProps {
  id: string
  name: string
  editing: boolean
  onEditingChange: (editing: boolean) => void
}

/** Column name that turns into an input to rename it (Enter or blur saves, Escape cancels). */
export function ColumnTitle({ id, name, editing, onEditingChange }: ColumnTitleProps) {
  const rename = useRenameStatus()
  const [draft, setDraft] = useState(name)
  const [error, setError] = useState<string | null>(null)

  function start() {
    setDraft(name)
    setError(null)
    onEditingChange(true)
  }

  function cancel() {
    rename.reset()
    setError(null)
    onEditingChange(false)
  }

  function submit() {
    // Enter then the resulting blur must not save twice.
    if (rename.isPending) return
    const trimmed = draft.trim()
    if (trimmed === name) {
      cancel()
      return
    }
    const problem = validateStatusName(trimmed)
    if (problem) {
      setError(problem)
      return
    }
    rename.mutate(
      { id, name: trimmed },
      {
        onSuccess: () => {
          onEditingChange(false)
        },
        onError: (err) => {
          setError(errorMessage(err))
        },
      },
    )
  }

  if (!editing) {
    return (
      <h2 className="min-w-0 flex-1">
        <button
          type="button"
          className="w-full truncate rounded px-1 text-left text-sm font-semibold hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
          // Says what the button does; the visible name is part of it (WCAG 2.5.3).
          aria-label={`Rename column ${name}`}
          title="Rename column"
          onClick={start}
        >
          {name}
        </button>
      </h2>
    )
  }

  return (
    <div className="min-w-0 flex-1">
      <Input
        aria-label="Column name"
        // Replaces the name the user just activated to rename; focus must land in it.
        // eslint-disable-next-line jsx-a11y/no-autofocus
        autoFocus
        value={draft}
        disabled={rename.isPending}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-rename-error` : undefined}
        className="h-7 text-sm font-semibold"
        onChange={(event) => {
          setDraft(event.target.value)
        }}
        onBlur={submit}
        onKeyDown={(event) => {
          if (event.key === 'Enter') {
            event.preventDefault()
            submit()
          } else if (event.key === 'Escape') {
            event.preventDefault()
            event.stopPropagation()
            cancel()
          }
        }}
      />
      {error && (
        <p id={`${id}-rename-error`} role="alert" className="mt-1 text-xs text-destructive">
          {error}
        </p>
      )}
    </div>
  )
}
