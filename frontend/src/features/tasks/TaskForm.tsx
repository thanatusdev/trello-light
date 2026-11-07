import { zodResolver } from '@hookform/resolvers/zod'
import { format, parseISO } from 'date-fns'
import { useMemo, useState } from 'react'
import { Controller, useForm } from 'react-hook-form'

import { errorMessage } from '@/api/errors'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { DialogFooter } from '@/components/ui/dialog'
import {
  Field,
  FieldContent,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
} from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import type { ColumnSummary } from '@/features/board/api'

import type { Task } from './api'
import { AssigneeCombobox } from './AssigneeCombobox'
import { completionTarget } from './completion'
import { DueDatePicker } from './DueDatePicker'
import { useDeleteTask, useSaveTask } from './mutations'
import {
  isAllowedDueDate,
  makeTaskSchema,
  type TaskFormInput,
  type TaskFormValues,
  utcToday,
} from './schema'

interface TaskFormProps {
  /** The task to edit, or null to create one. */
  task: Task | null
  columns: ColumnSummary[]
  /** Column a new task starts in. */
  defaultStatusId?: string | null
  onDone: () => void
}

export function TaskForm({ task, columns, defaultStatusId, onDone }: TaskFormProps) {
  const isEdit = task !== null
  const today = utcToday()
  const schema = useMemo(
    () => makeTaskSchema({ originalDueDate: task?.due_date ?? null, today }),
    [task?.due_date, today],
  )
  const {
    register,
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<TaskFormInput, unknown, TaskFormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      title: task?.title ?? '',
      description: task?.description ?? '',
      status_id: task?.status_id ?? defaultStatusId ?? columns[0]?.id ?? '',
      assignee_id: task?.assignee?.id ?? null,
      due_date: task?.due_date ?? null,
    },
  })

  const wasComplete = columns.find((column) => column.id === task?.status_id)?.is_done ?? false
  const [complete, setComplete] = useState(wasComplete)
  const target = completionTarget(columns, !wasComplete)

  const save = useSaveTask()
  const remove = useDeleteTask()

  const onSubmit = handleSubmit((values) => {
    const moveToStatusId = complete !== wasComplete ? (target?.id ?? null) : null
    save.mutate({ original: task, values, moveToStatusId }, { onSuccess: onDone })
  })

  const invalid = (name: keyof TaskFormInput) => (errors[name] ? true : undefined)

  return (
    <form noValidate onSubmit={(event) => void onSubmit(event)}>
      <FieldGroup>
        {save.isError && (
          <Alert variant="destructive">
            <AlertDescription>{errorMessage(save.error)}</AlertDescription>
          </Alert>
        )}

        <Field data-invalid={invalid('title')}>
          <FieldLabel htmlFor="task-title">Title</FieldLabel>
          <Input
            id="task-title"
            // The form opens on the user's "New task" action; start them in its first field.
            // eslint-disable-next-line jsx-a11y/no-autofocus
            autoFocus={!isEdit}
            aria-invalid={invalid('title')}
            {...register('title')}
          />
          <FieldError errors={[errors.title]} />
        </Field>

        <Field data-invalid={invalid('description')}>
          <FieldLabel htmlFor="task-description">Description</FieldLabel>
          <Textarea
            id="task-description"
            rows={4}
            aria-invalid={invalid('description')}
            {...register('description')}
          />
          <FieldError errors={[errors.description]} />
        </Field>

        {!isEdit && (
          <Field data-invalid={invalid('status_id')}>
            <FieldLabel htmlFor="task-status">Column</FieldLabel>
            <Controller
              control={control}
              name="status_id"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger
                    id="task-status"
                    className="w-full"
                    aria-invalid={invalid('status_id')}
                  >
                    <SelectValue placeholder="Choose a column" />
                  </SelectTrigger>
                  <SelectContent>
                    {columns.map((column) => (
                      <SelectItem key={column.id} value={column.id}>
                        {column.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
            <FieldError errors={[errors.status_id]} />
          </Field>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <Field data-invalid={invalid('assignee_id')}>
            <FieldLabel htmlFor="task-assignee">Assignee</FieldLabel>
            <Controller
              control={control}
              name="assignee_id"
              render={({ field }) => (
                <AssigneeCombobox
                  id="task-assignee"
                  value={field.value}
                  onChange={field.onChange}
                  fallbackName={task?.assignee?.full_name}
                />
              )}
            />
            <FieldError errors={[errors.assignee_id]} />
          </Field>

          <Field data-invalid={invalid('due_date')}>
            <FieldLabel htmlFor="task-due">Due date</FieldLabel>
            <Controller
              control={control}
              name="due_date"
              render={({ field }) => (
                <DueDatePicker
                  id="task-due"
                  aria-label="due date"
                  value={field.value}
                  onChange={field.onChange}
                  invalid={invalid('due_date')}
                  placeholder="No due date"
                  isDisabled={(date) =>
                    !isAllowedDueDate(date, { today, originalDueDate: task?.due_date })
                  }
                />
              )}
            />
            <FieldError errors={[errors.due_date]} />
          </Field>
        </div>

        {isEdit && (
          <Field orientation="horizontal">
            <Checkbox
              id="task-complete"
              checked={complete}
              disabled={target === null}
              aria-describedby={target === null ? 'task-complete-reason' : undefined}
              onCheckedChange={(value) => {
                setComplete(value === true)
              }}
            />
            <FieldContent>
              <FieldLabel htmlFor="task-complete">Mark complete</FieldLabel>
              {/* Visible text rather than a tooltip: a disabled control can't be focused or
                  hovered, and touch screens have no hover at all. */}
              {target === null && (
                <FieldDescription id="task-complete-reason">
                  {wasComplete
                    ? 'Add a column that is not marked done to reopen tasks.'
                    : 'Add a column that marks tasks complete first.'}
                </FieldDescription>
              )}
              {task.completed_at && complete && (
                <FieldDescription>
                  Completed {format(parseISO(task.completed_at), 'PP')}
                </FieldDescription>
              )}
              {complete !== wasComplete && target && (
                <FieldDescription>Saving moves it to “{target.name}”.</FieldDescription>
              )}
            </FieldContent>
          </Field>
        )}
      </FieldGroup>

      <DialogFooter className="mt-6 gap-2 sm:justify-between">
        {isEdit ? (
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button type="button" variant="destructive">
                Delete
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete this task?</AlertDialogTitle>
                <AlertDialogDescription>
                  “{task.title}” will be permanently deleted. This can’t be undone.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  variant="destructive"
                  onClick={() => {
                    remove.mutate(task.id)
                    onDone()
                  }}
                >
                  Delete task
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        ) : (
          <span />
        )}
        <div className="flex gap-2">
          <Button type="button" variant="outline" onClick={onDone}>
            Cancel
          </Button>
          <Button type="submit" disabled={save.isPending}>
            {save.isPending ? 'Saving…' : isEdit ? 'Save' : 'Create task'}
          </Button>
        </div>
      </DialogFooter>
    </form>
  )
}
