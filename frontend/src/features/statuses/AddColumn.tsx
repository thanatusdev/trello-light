import { PlusIcon } from 'lucide-react'
import { type SyntheticEvent, useState } from 'react'

import { errorMessage } from '@/api/errors'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Field, FieldError, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'

import { useCreateStatus, validateStatusName } from './api'

/** "+ Add column" tile at the end of the board; expands into a small form. */
export function AddColumn() {
  const create = useCreateStatus()
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [isDone, setIsDone] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function reset() {
    setOpen(false)
    setName('')
    setIsDone(false)
    setError(null)
    create.reset()
  }

  function submit(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault()
    const problem = validateStatusName(name)
    if (problem) {
      setError(problem)
      return
    }
    create.mutate(
      { name: name.trim(), is_done: isDone },
      {
        onSuccess: reset,
        onError: (err) => {
          setError(errorMessage(err))
        },
      },
    )
  }

  if (!open) {
    return (
      <Button
        variant="outline"
        className="h-11 w-72 shrink-0 snap-start justify-start border-dashed"
        onClick={() => {
          setOpen(true)
        }}
      >
        <PlusIcon aria-hidden />
        Add column
      </Button>
    )
  }

  return (
    <form
      noValidate
      onSubmit={submit}
      aria-label="New column"
      className="flex w-72 shrink-0 snap-start flex-col gap-3 self-start rounded-xl border bg-muted/50 p-3"
    >
      <Field data-invalid={error ? true : undefined}>
        <FieldLabel htmlFor="new-column-name">Column name</FieldLabel>
        <Input
          id="new-column-name"
          // The field only appears after the user presses "Add column"; focus follows them.
          // eslint-disable-next-line jsx-a11y/no-autofocus
          autoFocus
          value={name}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? 'new-column-name-error' : undefined}
          onChange={(event) => {
            setName(event.target.value)
          }}
          onKeyDown={(event) => {
            if (event.key === 'Escape') reset()
          }}
        />
        {error && <FieldError id="new-column-name-error">{error}</FieldError>}
      </Field>
      <Field orientation="horizontal">
        <Checkbox
          id="new-column-done"
          checked={isDone}
          onCheckedChange={(value) => {
            setIsDone(value === true)
          }}
        />
        <FieldLabel htmlFor="new-column-done" className="font-normal">
          Marks tasks complete
        </FieldLabel>
      </Field>
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={create.isPending}>
          {create.isPending ? 'Adding…' : 'Add column'}
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={reset}>
          Cancel
        </Button>
      </div>
    </form>
  )
}
