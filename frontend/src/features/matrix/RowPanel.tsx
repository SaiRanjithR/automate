import {
  ChevronDown,
  FileSearch,
  History,
  Pencil,
  RefreshCw,
  ShieldCheck,
  Undo2,
} from 'lucide-react'
import { useImperativeHandle, useState, type Ref } from 'react'
import { toast } from 'sonner'

import { StatusChip, type ComplianceStatus } from '@/components/common/StatusChip'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { JobProgress } from '@/features/jobs/JobProgress'
import { DiffView } from '@/features/matrix/DiffView'
import {
  useHistory,
  useInvalidateProject,
  usePatchResponse,
  useRedraft,
} from '@/features/projects/api'
import type { Citation, RequirementRow } from '@/features/projects/types'
import { apiUrl, errorMessage } from '@/lib/api'
import { cn } from '@/lib/utils'

export type PanelHandle = { approve: () => void; edit: () => void; redraft: () => void }

const STATUS_OPTIONS: { value: ComplianceStatus; label: string }[] = [
  { value: 'fully_compliant', label: 'Fully compliant' },
  { value: 'partially_compliant', label: 'Partially compliant' },
  { value: 'compliant_with_customisation', label: 'Compliant with customisation' },
  { value: 'non_compliant', label: 'Non-compliant' },
  { value: 'gap', label: 'Gap' },
]
const SEVERITY_CLASS = {
  high: 'border-status-gap/60 text-status-gap',
  medium: 'border-status-partial/60 text-status-partial',
  low: 'border-border text-muted-foreground',
} as const
const ACTION_LABEL: Record<string, string> = {
  ai_draft: 'AI draft',
  edit: 'Edited',
  approve: 'Approved',
  unapprove: 'Approval removed',
  unapproved_by_addendum: 'Unapproved by addendum',
}

type RowPanelProps = { projectId: number; row: RequirementRow; ref?: Ref<PanelHandle> }

export function RowPanel({ projectId, row, ref }: RowPanelProps) {
  const response = row.response
  const patch = usePatchResponse(projectId)
  const redraft = useRedraft()
  const invalidate = useInvalidateProject()
  const history = useHistory(response?.id)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const [approveOpen, setApproveOpen] = useState(false)
  const [reason, setReason] = useState('')
  const [redraftOpen, setRedraftOpen] = useState(false)
  const [hint, setHint] = useState('')
  const [redraftJob, setRedraftJob] = useState<number | null>(null)
  const [sourceOpen, setSourceOpen] = useState(false)

  const highIssues = (response?.review_issues ?? []).filter((i) => i.severity === 'high')
  const citations = (response?.citations ?? []) as Citation[]

  const save = (body: Parameters<typeof patch.mutate>[0]['patch'], message: string) => {
    if (!response) return
    patch.mutate(
      { responseId: response.id, patch: body },
      { onSuccess: () => toast.success(message), onError: (e) => toast.error(errorMessage(e)) },
    )
  }

  const approve = () => {
    if (!response) return
    if (highIssues.length) {
      setApproveOpen(true)
      return
    }
    save({ approved: true }, `${row.req_code} approved`)
  }

  const startEdit = () => {
    setDraft(response?.answer ?? '')
    setEditing(true)
  }

  useImperativeHandle(ref, () => ({
    approve,
    edit: startEdit,
    redraft: () => setRedraftOpen(true),
  }))

  return (
    <aside
      aria-label={`Requirement ${row.req_code}`}
      className="flex flex-col gap-4 rounded-lg border border-border p-4 lg:sticky lg:top-4 lg:max-h-[calc(100svh-2rem)] lg:overflow-y-auto"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-sm font-semibold">{row.req_code}</span>
        <Badge variant="outline">{row.type === 'mandatory' ? 'Mandatory' : 'Optional'}</Badge>
        <StatusChip status={(response?.status ?? 'pending') as ComplianceStatus} />
        {response?.approved ? (
          <Badge variant="secondary" className="gap-1">
            <ShieldCheck aria-hidden="true" className="size-3" /> Approved
          </Badge>
        ) : null}
        {response?.needs_review ? <Badge variant="outline">Changed by addendum</Badge> : null}
      </div>
      <div className="flex flex-col gap-2">
        <p className="text-sm font-medium">{row.text}</p>
        <blockquote className="border-l-2 border-border pl-3 font-serif text-sm text-muted-foreground">
          “{row.source_quote}”
        </blockquote>
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span>
            {row.section_path}
            {row.page ? ` · page ${row.page}` : ''}
          </span>
          {row.criterion_name ? (
            <Badge variant="outline">Scored under: {row.criterion_name}</Badge>
          ) : null}
          {row.page && row.rfp_file_id ? (
            <Button
              variant="link"
              size="xs"
              className="h-auto p-0"
              onClick={() => setSourceOpen(true)}
            >
              <FileSearch aria-hidden="true" /> View in RFP
            </Button>
          ) : null}
        </div>
        {row.version_status === 'modified' ? <DiffView requirementId={row.id} /> : null}
      </div>

      <section className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">Answer</h3>
          {response?.review_score !== null && response?.review_score !== undefined ? (
            <Badge variant="outline" className="tabular-nums">
              Review {response.review_score}
            </Badge>
          ) : null}
        </div>
        {editing ? (
          <div className="flex flex-col gap-2">
            <Textarea
              aria-label="Answer"
              rows={8}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
            />
            <div className="flex gap-2">
              <Button
                size="sm"
                disabled={patch.isPending}
                onClick={() => {
                  save(
                    {
                      answer: draft,
                      status: response?.status === 'gap' ? 'fully_compliant' : undefined,
                    },
                    'Answer saved',
                  )
                  setEditing(false)
                }}
              >
                Save
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
                Cancel
              </Button>
            </div>
          </div>
        ) : response?.answer ? (
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{response.answer}</p>
        ) : response?.status === 'gap' ? (
          <div className="flex flex-col gap-2 rounded-md border-2 border-status-gap/70 p-3">
            <p className="text-sm font-semibold">No evidence found</p>
            <p className="text-sm text-muted-foreground">
              {response.gap_reason ?? 'Your documents do not cover this requirement.'}
            </p>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="outline" onClick={startEdit}>
                Write manually
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => save({ status: 'non_compliant' }, 'Marked non-compliant')}
              >
                Mark non-compliant
              </Button>
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Not drafted yet.</p>
        )}
        {response?.answer && response.gap_reason && response.status !== 'fully_compliant' ? (
          <p className="text-xs text-status-partial">{response.gap_reason}</p>
        ) : null}
      </section>

      {citations.length ? (
        <section className="flex flex-col gap-2">
          <h3 className="text-sm font-semibold">
            {citations.every((c) => c.kind === 'rfp_clause')
              ? 'Commitment to the RFP clause'
              : 'Evidence'}
          </h3>
          <ul className="flex flex-col gap-2">
            {citations.map((c, index) => (
              <li
                key={`${c.chunk_id}-${index}`}
                className={cn(
                  'rounded-md p-2 text-xs',
                  c.kind === 'rfp_clause' ? 'border border-dashed border-border' : 'bg-muted/60',
                )}
              >
                <p className="mb-1 flex flex-wrap items-center gap-1.5 font-medium">
                  {c.filename}
                  {c.page ? ` · page ${c.page}` : ''}
                  {c.outcome === 'won' ? (
                    <Badge variant="outline" className="border-status-full/50 text-status-full">
                      Won bid
                    </Badge>
                  ) : null}
                </p>
                <p className="font-serif">“{c.quote}”</p>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {response?.review_issues.length ? (
        <section className="flex flex-col gap-2">
          <h3 className="text-sm font-semibold">Review issues</h3>
          <ul className="flex flex-col gap-1.5">
            {response.review_issues.map((issue, index) => (
              <li
                key={index}
                className={cn(
                  'rounded-md border px-2 py-1.5 text-xs',
                  SEVERITY_CLASS[issue.severity],
                )}
              >
                <span className="font-medium capitalize">{issue.severity}</span> · {issue.message}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {response ? (
        <div className="flex flex-col gap-3 border-t border-border pt-3">
          <div className="flex flex-wrap gap-2">
            {response.approved ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() => save({ approved: false }, 'Approval removed')}
              >
                <Undo2 aria-hidden="true" /> Unapprove
              </Button>
            ) : (
              <Button
                size="sm"
                disabled={!response.answer && response.status !== 'non_compliant'}
                onClick={approve}
              >
                <ShieldCheck aria-hidden="true" />{' '}
                {highIssues.length ? 'Approve with reason' : 'Approve'}
              </Button>
            )}
            <Button variant="outline" size="sm" onClick={startEdit}>
              <Pencil aria-hidden="true" /> Edit
            </Button>
            <Button variant="outline" size="sm" onClick={() => setRedraftOpen(true)}>
              <RefreshCw aria-hidden="true" /> Re-draft
            </Button>
          </div>
          <div className="flex max-w-xs flex-col gap-1.5">
            <Label htmlFor={`status-${row.id}`} className="text-xs">
              Compliance status
            </Label>
            <Select
              value={response.status === 'pending' ? undefined : response.status}
              onValueChange={(value) => save({ status: value }, 'Status updated')}
            >
              <SelectTrigger id={`status-${row.id}`} size="sm">
                <SelectValue placeholder="Not drafted" />
              </SelectTrigger>
              <SelectContent>
                {STATUS_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {redraftJob ? (
            <JobProgress
              jobId={redraftJob}
              onDone={(job) => {
                invalidate(projectId)
                if (job.status === 'succeeded') toast.success(`${row.req_code} re-drafted`)
              }}
            />
          ) : null}
          <Collapsible>
            <CollapsibleTrigger asChild>
              <Button variant="ghost" size="sm" className="self-start">
                <History aria-hidden="true" /> History <ChevronDown aria-hidden="true" />
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <ul className="mt-2 flex flex-col gap-1 text-xs text-muted-foreground">
                {(history.data ?? []).map((event) => (
                  <li key={event.id}>
                    {new Date(event.at).toLocaleString('en-IN')} ·{' '}
                    {ACTION_LABEL[event.action] ?? event.action} ·{' '}
                    {event.actor.startsWith('model:')
                      ? event.actor.replace('model:', 'AI ')
                      : 'You'}
                  </li>
                ))}
                {history.data?.length === 0 ? <li>No changes yet.</li> : null}
              </ul>
            </CollapsibleContent>
          </Collapsible>
          <p className="text-xs text-muted-foreground">
            Shortcuts: J / K move · A approve · E edit · R re-draft · / search
          </p>
        </div>
      ) : null}

      <Dialog open={approveOpen} onOpenChange={setApproveOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Approve with open issues?</DialogTitle>
            <DialogDescription>
              The review found {highIssues.length} high-severity issue(s). Say why this answer is
              acceptable; the reason is kept in the audit trail.
            </DialogDescription>
          </DialogHeader>
          <ul className="list-disc pl-5 text-sm">
            {highIssues.map((issue, index) => (
              <li key={index}>{issue.message}</li>
            ))}
          </ul>
          <Label htmlFor="override-reason">Reason</Label>
          <Input
            id="override-reason"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
          <DialogFooter>
            <Button variant="ghost" onClick={() => setApproveOpen(false)}>
              Cancel
            </Button>
            <Button
              disabled={!reason.trim()}
              onClick={() => {
                save({ approved: true, override_reason: reason }, `${row.req_code} approved`)
                setApproveOpen(false)
              }}
            >
              Approve
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={redraftOpen} onOpenChange={setRedraftOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Re-draft {row.req_code}</DialogTitle>
            <DialogDescription>
              Optionally tell the drafter what to focus on. The current answer will be replaced.
            </DialogDescription>
          </DialogHeader>
          <Label htmlFor="redraft-hint">Hint (optional)</Label>
          <Input
            id="redraft-hint"
            placeholder="e.g. mention the Mysuru project"
            value={hint}
            onChange={(event) => setHint(event.target.value)}
          />
          <DialogFooter>
            <Button variant="ghost" onClick={() => setRedraftOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => {
                if (!response) return
                redraft.mutate(
                  { responseId: response.id, hint },
                  {
                    onSuccess: (r) => setRedraftJob(r.job_id),
                    onError: (e) => toast.error(errorMessage(e)),
                  },
                )
                setRedraftOpen(false)
              }}
            >
              Re-draft
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={sourceOpen} onOpenChange={setSourceOpen}>
        <DialogContent className="max-h-[90svh] overflow-y-auto sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>
              {row.req_code} in the RFP · page {row.page}
            </DialogTitle>
            <DialogDescription>
              The requirement is highlighted on the original page.
            </DialogDescription>
          </DialogHeader>
          {sourceOpen ? (
            <img
              src={apiUrl(`/projects/${projectId}/requirements/${row.id}/source.png`)}
              alt={`Page ${row.page ?? ''} of the RFP with ${row.req_code} highlighted`}
              className="w-full rounded-md border border-border"
            />
          ) : null}
        </DialogContent>
      </Dialog>
    </aside>
  )
}
