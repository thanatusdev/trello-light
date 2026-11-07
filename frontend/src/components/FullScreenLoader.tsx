import { Loader2Icon } from 'lucide-react'

export function FullScreenLoader() {
  return (
    <div role="status" aria-label="Loading" className="flex min-h-svh items-center justify-center">
      <Loader2Icon aria-hidden className="size-6 animate-spin text-muted-foreground" />
    </div>
  )
}
