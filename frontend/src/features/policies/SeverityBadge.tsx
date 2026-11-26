import { AlertOctagon, AlertTriangle, Info } from 'lucide-react'

import type { Severity } from '@/features/policies/types'
import { cn } from '@/lib/utils'

const STYLE = {
  high: {
    icon: AlertOctagon,
    label: 'High',
    className: 'border-status-gap/60 text-status-gap bg-status-gap/10',
  },
  medium: {
    icon: AlertTriangle,
    label: 'Medium',
    className: 'border-status-partial/60 text-status-partial bg-status-partial/10',
  },
  low: { icon: Info, label: 'Low', className: 'border-border text-muted-foreground bg-muted' },
} as const

export function SeverityBadge({ severity, className }: { severity: Severity; className?: string }) {
  const style = STYLE[severity]
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium',
        style.className,
        className,
      )}
    >
      <style.icon aria-hidden="true" className="size-3" />
      {style.label}
    </span>
  )
}
