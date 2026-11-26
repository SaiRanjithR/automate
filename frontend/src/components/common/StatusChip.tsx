import {
  AlertTriangle,
  Check,
  CircleDashed,
  Contrast,
  Sparkles,
  Wrench,
  X,
  type LucideIcon,
} from 'lucide-react'

import { cn } from '@/lib/utils'

export type ComplianceStatus =
  | 'fully_compliant'
  | 'partially_compliant'
  | 'compliant_with_customisation'
  | 'non_compliant'
  | 'gap'
  | 'draft'
  | 'pending'

type StatusStyle = { label: string; icon: LucideIcon; className: string }

const STATUS_STYLES: Record<ComplianceStatus, StatusStyle> = {
  fully_compliant: {
    label: 'Full',
    icon: Check,
    className: 'border-status-full/50 bg-status-full/10 text-status-full',
  },
  partially_compliant: {
    label: 'Partial',
    icon: Contrast,
    className: 'border-status-partial/50 bg-status-partial/10 text-status-partial',
  },
  compliant_with_customisation: {
    label: 'Custom',
    icon: Wrench,
    className: 'border-status-custom/50 bg-status-custom/10 text-status-custom',
  },
  non_compliant: {
    label: 'Non-compliant',
    icon: X,
    className: 'border-status-noncompliant/50 bg-status-noncompliant/10 text-status-noncompliant',
  },
  gap: {
    label: 'Gap',
    icon: AlertTriangle,
    className: 'border-status-gap bg-background font-semibold text-status-gap',
  },
  draft: {
    label: 'AI draft',
    icon: Sparkles,
    className: 'border-status-draft/50 bg-status-draft/10 text-status-draft',
  },
  pending: {
    label: 'Pending',
    icon: CircleDashed,
    className: 'border-border bg-muted text-muted-foreground',
  },
}

type StatusChipProps = {
  status: ComplianceStatus
  className?: string
}

/** Compliance status shown with icon + text + colour — never colour alone. */
export function StatusChip({ status, className }: StatusChipProps) {
  const { label, icon: Icon, className: statusClass } = STATUS_STYLES[status]
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium',
        statusClass,
        className,
      )}
    >
      <Icon aria-hidden="true" className="size-3" />
      {label}
    </span>
  )
}
