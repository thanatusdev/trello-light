import { toast } from 'sonner'

import { errorMessage } from '@/api/errors'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'

import { useDeleteStatus } from './api'

interface DeleteColumnDialogProps {
  id: string
  name: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

/** Confirms deleting a column. The API refuses columns that still have tasks; say why. */
export function DeleteColumnDialog({ id, name, open, onOpenChange }: DeleteColumnDialogProps) {
  const remove = useDeleteStatus()

  return (
    <AlertDialog
      open={open}
      onOpenChange={(next) => {
        if (!next) remove.reset()
        onOpenChange(next)
      }}
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete the “{name}” column?</AlertDialogTitle>
          <AlertDialogDescription>
            Only empty columns can be deleted. Tasks are never deleted with a column.
          </AlertDialogDescription>
        </AlertDialogHeader>
        {remove.isError && (
          <Alert variant="destructive">
            <AlertDescription>{errorMessage(remove.error)}</AlertDescription>
          </Alert>
        )}
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          {/* A plain button: the dialog must stay open to show a refusal. */}
          <Button
            variant="destructive"
            disabled={remove.isPending}
            onClick={() => {
              remove.mutate(id, {
                onSuccess: () => {
                  onOpenChange(false)
                  toast.success(`Deleted the “${name}” column.`)
                },
              })
            }}
          >
            {remove.isPending ? 'Deleting…' : 'Delete column'}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
