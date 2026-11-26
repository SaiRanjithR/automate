import { Skeleton } from '@/components/ui/skeleton'

type LoadingRowsProps = {
  rows?: number
  label?: string
}

export function LoadingRows({ rows = 5, label = 'Loading' }: LoadingRowsProps) {
  return (
    <div role="status" aria-busy="true" aria-label={label} className="flex flex-col gap-2">
      {Array.from({ length: rows }, (_, index) => (
        <Skeleton key={index} className="h-11 w-full" />
      ))}
    </div>
  )
}
