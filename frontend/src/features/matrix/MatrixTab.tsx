import { ClipboardList, Search, ShieldCheck } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router'

import { EmptyState } from '@/components/common/EmptyState'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingRows } from '@/components/common/LoadingRows'
import { StatusChip, type ComplianceStatus } from '@/components/common/StatusChip'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useKnowledge } from '@/features/company/api'
import { JobProgress } from '@/features/jobs/JobProgress'
import { RowPanel, type PanelHandle } from '@/features/matrix/RowPanel'
import { DraftAllButton } from '@/features/overview/DraftCard'
import { useCriteria, useInvalidateProject, useRequirements } from '@/features/projects/api'
import type { ProjectSummary } from '@/features/projects/types'
import { errorMessage } from '@/lib/api'
import { useHotkeys } from '@/lib/keyboard'
import type { RequirementFilters } from '@/lib/queryKeys'
import { cn } from '@/lib/utils'

const CHIPS: { key: string; label: string; status?: string; className: string }[] = [
  { key: 'total', label: 'requirements', className: 'border-border' },
  {
    key: 'fully_compliant',
    label: 'compliant',
    status: 'fully_compliant',
    className: 'border-status-full/50 text-status-full',
  },
  {
    key: 'partially_compliant',
    label: 'partial',
    status: 'partially_compliant',
    className: 'border-status-partial/50 text-status-partial',
  },
  {
    key: 'gap',
    label: 'gaps',
    status: 'gap',
    className: 'border-status-gap/60 font-semibold text-status-gap',
  },
  {
    key: 'pending',
    label: 'not drafted',
    status: 'pending',
    className: 'border-border text-muted-foreground',
  },
  {
    key: 'approved',
    label: 'approved',
    status: 'approved',
    className: 'border-primary/50 text-primary',
  },
  {
    key: 'changed',
    label: 'changed by addendum',
    className: 'border-status-custom/50 text-status-custom',
  },
]
const STATUS_FILTERS = [
  { value: 'all', label: 'All statuses' },
  { value: 'fully_compliant', label: 'Fully compliant' },
  { value: 'partially_compliant', label: 'Partially compliant' },
  { value: 'compliant_with_customisation', label: 'With customisation' },
  { value: 'non_compliant', label: 'Non-compliant' },
  { value: 'gap', label: 'Gaps' },
  { value: 'pending', label: 'Not drafted' },
  { value: 'approved', label: 'Approved' },
]

export function MatrixTab({ project }: { project: ProjectSummary }) {
  const [params, setParams] = useSearchParams()
  const [search, setSearch] = useState(params.get('q') ?? '')
  const [draftJob, setDraftJob] = useState<number | null>(null)
  const panelRef = useRef<PanelHandle>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const invalidate = useInvalidateProject()
  const criteria = useCriteria(project.id)
  const knowledge = useKnowledge(false)
  const knowledgeEmpty =
    knowledge.data !== undefined && knowledge.data.filter((d) => d.status === 'ready').length === 0

  const filters: RequirementFilters = useMemo(
    () => ({
      status: params.get('status') ?? undefined,
      mandatory: params.get('mandatory') === '1' ? true : undefined,
      criterion_id: params.get('criterion') ? Number(params.get('criterion')) : undefined,
      has_issues: params.get('issues') === '1' ? true : undefined,
      version_status: params.get('changed') === '1' ? 'modified,added' : undefined,
      q: params.get('q') ?? undefined,
    }),
    [params],
  )
  const { data, isPending, error, refetch } = useRequirements(project.id, filters)
  const items = useMemo(() => data?.items ?? [], [data])
  const selectedId = params.get('row') ? Number(params.get('row')) : null
  const selected = items.find((r) => r.id === selectedId) ?? null

  const update = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params)
    for (const [key, value] of Object.entries(changes)) {
      if (value === null || value === '') next.delete(key)
      else next.set(key, value)
    }
    setParams(next, { replace: true })
  }

  useEffect(() => {
    const timer = window.setTimeout(() => {
      if ((params.get('q') ?? '') !== search) update({ q: search || null })
    }, 300)
    return () => window.clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- debounce only on input changes
  }, [search])

  const move = (delta: number) => {
    if (!items.length) return
    const index = items.findIndex((r) => r.id === selectedId)
    const next = items[Math.max(0, Math.min(items.length - 1, index === -1 ? 0 : index + delta))]
    if (next) {
      update({ row: String(next.id) })
      document.getElementById(`row-${next.id}`)?.scrollIntoView({ block: 'nearest' })
    }
  }
  const hotkeys = useMemo(
    () => ({
      j: () => move(1),
      k: () => move(-1),
      a: () => panelRef.current?.approve(),
      e: () => panelRef.current?.edit(),
      r: () => panelRef.current?.redraft(),
      '/': () => searchRef.current?.focus(),
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- move reads current items via closure
    [items, selectedId, params],
  )
  useHotkeys(hotkeys)

  const summary = data?.summary ?? {}
  const nothingDrafted = (summary.pending ?? 0) === (summary.total ?? 0) && (summary.total ?? 0) > 0

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        {CHIPS.map((chip) => {
          const active = chip.status
            ? filters.status === chip.status
            : chip.key === 'changed'
              ? params.get('changed') === '1'
              : !filters.status
          return (
            <button
              key={chip.key}
              type="button"
              aria-pressed={active}
              onClick={() =>
                chip.key === 'changed'
                  ? update({ changed: params.get('changed') === '1' ? null : '1' })
                  : update({
                      status: chip.status && filters.status !== chip.status ? chip.status : null,
                    })
              }
              className={cn(
                'rounded-md border px-2.5 py-1 text-xs transition-colors hover:bg-muted',
                chip.className,
                active && 'ring-2 ring-ring/40',
              )}
            >
              <span className="tabular-nums">{summary[chip.key] ?? 0}</span> {chip.label}
            </button>
          )
        })}
        <div className="ml-auto">
          {draftJob ? null : <DraftAllButton projectId={project.id} onStarted={setDraftJob} />}
        </div>
      </div>
      {knowledgeEmpty ? (
        <Alert variant="destructive">
          <AlertTitle>No documents to draft from</AlertTitle>
          <AlertDescription>
            Answers are written only from your own documents. Upload past proposals (mark the won
            ones), case studies and your company profile in the{' '}
            <Link to="/knowledge" className="underline">
              knowledge base
            </Link>
            , then click Draft all answers again. Until then only commitments to RFP clauses can be
            drafted.
          </AlertDescription>
        </Alert>
      ) : null}
      {draftJob ? (
        <JobProgress
          jobId={draftJob}
          onRetry={setDraftJob}
          onDone={() => {
            invalidate(project.id)
            setDraftJob(null)
          }}
        />
      ) : null}

      <div className="flex flex-wrap items-end gap-3">
        <div className="relative min-w-56 flex-1">
          <Search
            aria-hidden="true"
            className="absolute top-2 left-2.5 size-4 text-muted-foreground"
          />
          <Input
            ref={searchRef}
            aria-label="Search requirements"
            placeholder="Search requirements and answers ( / )"
            className="pl-8"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <Select
          value={filters.status ?? 'all'}
          onValueChange={(value) => update({ status: value === 'all' ? null : value })}
        >
          <SelectTrigger aria-label="Filter by status" className="w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {STATUS_FILTERS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={params.get('criterion') ?? 'all'}
          onValueChange={(value) => update({ criterion: value === 'all' ? null : value })}
        >
          <SelectTrigger aria-label="Filter by scoring criterion" className="w-56">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All scoring criteria</SelectItem>
            {(criteria.data ?? []).map((c) => (
              <SelectItem key={c.id} value={String(c.id)}>
                {c.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="flex items-center gap-2">
          <Switch
            id="mandatory"
            checked={filters.mandatory === true}
            onCheckedChange={(on) => update({ mandatory: on ? '1' : null })}
          />
          <Label htmlFor="mandatory" className="text-sm">
            Mandatory only
          </Label>
        </div>
        <div className="flex items-center gap-2">
          <Switch
            id="issues"
            checked={filters.has_issues === true}
            onCheckedChange={(on) => update({ issues: on ? '1' : null })}
          />
          <Label htmlFor="issues" className="text-sm">
            Has review issues
          </Label>
        </div>
      </div>

      {isPending ? (
        <LoadingRows rows={8} label="Loading requirements" />
      ) : error ? (
        <ErrorState message={errorMessage(error)} onRetry={() => void refetch()} />
      ) : (data?.summary.total ?? 0) === 0 ? (
        <EmptyState
          icon={ClipboardList}
          title="No requirements yet"
          description={
            project.status === 'analysing'
              ? 'The RFP is still being analysed.'
              : 'No requirements were found in this RFP.'
          }
        />
      ) : (
        <div className={cn('grid gap-4', selected && 'lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]')}>
          <div className="overflow-hidden rounded-lg border border-border">
            {nothingDrafted ? (
              <p className="border-b border-border bg-primary/5 px-4 py-2 text-sm">
                Nothing drafted yet. Use <strong>Draft all answers</strong> to fill the matrix from
                your knowledge base.
              </p>
            ) : null}
            {items.length === 0 ? (
              <p className="p-6 text-center text-sm text-muted-foreground">
                No requirements match these filters.
              </p>
            ) : (
              <Table>
                <TableHeader className="bg-muted/50">
                  <TableRow>
                    <TableHead className="w-24">ID</TableHead>
                    <TableHead>Requirement</TableHead>
                    <TableHead className="hidden w-40 xl:table-cell">Scored under</TableHead>
                    <TableHead className="w-36">Status</TableHead>
                    <TableHead className="w-16 text-right">Review</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((row) => {
                    const status = (row.response?.status ?? 'pending') as ComplianceStatus
                    const isSelected = row.id === selectedId
                    return (
                      <TableRow
                        id={`row-${row.id}`}
                        key={row.id}
                        tabIndex={0}
                        aria-selected={isSelected}
                        onClick={() => update({ row: String(row.id) })}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter') update({ row: String(row.id) })
                        }}
                        className={cn(
                          'cursor-pointer',
                          isSelected && 'bg-primary/8 shadow-[inset_3px_0_0_var(--primary)]',
                          row.response?.approved && !isSelected && 'text-muted-foreground',
                        )}
                      >
                        <TableCell className="align-top font-mono text-xs">
                          {row.req_code}
                        </TableCell>
                        <TableCell className="align-top whitespace-normal">
                          <span className="line-clamp-2 text-sm">{row.text}</span>
                          <span className="mt-1 flex flex-wrap gap-1">
                            {row.type === 'mandatory' ? null : (
                              <Badge variant="outline">Optional</Badge>
                            )}
                            {row.version_status === 'modified' ? (
                              <Badge
                                variant="outline"
                                className="border-status-custom/50 text-status-custom"
                              >
                                Modified
                              </Badge>
                            ) : null}
                            {row.version_status === 'added' ? (
                              <Badge
                                variant="outline"
                                className="border-status-custom/50 text-status-custom"
                              >
                                New
                              </Badge>
                            ) : null}
                          </span>
                        </TableCell>
                        <TableCell className="hidden align-top text-xs whitespace-normal text-muted-foreground xl:table-cell">
                          {row.criterion_name ?? '—'}
                        </TableCell>
                        <TableCell className="align-top">
                          <div className="flex flex-col items-start gap-1">
                            <StatusChip status={status} />
                            {row.response?.approved ? (
                              <span className="inline-flex items-center gap-1 text-xs text-primary">
                                <ShieldCheck aria-hidden="true" className="size-3" /> Approved
                              </span>
                            ) : null}
                          </div>
                        </TableCell>
                        <TableCell className="text-right align-top text-xs tabular-nums">
                          {row.response?.review_score ?? '—'}
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            )}
          </div>
          {selected ? (
            <RowPanel key={selected.id} ref={panelRef} projectId={project.id} row={selected} />
          ) : null}
        </div>
      )}
    </div>
  )
}
