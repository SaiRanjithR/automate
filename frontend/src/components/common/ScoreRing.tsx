import { cn } from '@/lib/utils'

type ScoreRingProps = {
  value: number
  label: string
  size?: number
  className?: string
}

/** Circular 0-100 score. Colour shifts with the value; the number is always shown as text. */
export function ScoreRing({ value, label, size = 72, className }: ScoreRingProps) {
  const clamped = Math.max(0, Math.min(100, Math.round(value)))
  const radius = (size - 8) / 2
  const circumference = 2 * Math.PI * radius
  const tone =
    clamped >= 85 ? 'text-status-full' : clamped >= 60 ? 'text-status-partial' : 'text-status-gap'
  return (
    <div
      role="img"
      aria-label={`${label}: ${clamped} out of 100`}
      className={cn('relative inline-flex shrink-0 items-center justify-center', className)}
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          className="fill-none stroke-muted"
          strokeWidth={6}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          className={cn('fill-none stroke-current transition-all', tone)}
          strokeWidth={6}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - clamped / 100)}
        />
      </svg>
      <span className="absolute text-lg font-semibold tabular-nums">{clamped}</span>
    </div>
  )
}
