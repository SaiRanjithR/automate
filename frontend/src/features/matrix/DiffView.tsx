import { LoadingRows } from '@/components/common/LoadingRows'
import { useDiff } from '@/features/projects/api'
import { cn } from '@/lib/utils'

/** Word-level diff of a requirement changed by an addendum. */
export function DiffView({ requirementId }: { requirementId: number }) {
  const { data, isPending } = useDiff(requirementId, true)
  if (isPending) return <LoadingRows rows={1} />
  return (
    <p
      className="rounded-md bg-muted/60 p-2 text-sm leading-relaxed"
      aria-label="Changes from the addendum"
    >
      {(data ?? []).map((part, index) => (
        <span
          key={index}
          className={cn(
            part.op === 'insert' && 'rounded bg-status-full/15 px-0.5 font-medium text-status-full',
            part.op === 'delete' && 'rounded bg-status-gap/10 px-0.5 text-status-gap line-through',
          )}
        >
          {part.op === 'insert' ? <span className="sr-only">added: </span> : null}
          {part.op === 'delete' ? <span className="sr-only">removed: </span> : null}
          {part.text}{' '}
        </span>
      ))}
    </p>
  )
}
