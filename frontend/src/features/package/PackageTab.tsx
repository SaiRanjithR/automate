import {
  Download,
  FileSpreadsheet,
  FileText,
  FileType2,
  ListChecks,
  Package,
  Scale,
} from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { toast } from 'sonner'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingRows } from '@/components/common/LoadingRows'
import { ScoreRing } from '@/components/common/ScoreRing'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { JobProgress } from '@/features/jobs/JobProgress'
import {
  useConflicts,
  useGenerateOutline,
  useInvalidateProject,
  useOutline,
  usePackageInfo,
  useResolveConflict,
  useRunConsistency,
  useStartJob,
  useValidation,
} from '@/features/projects/api'
import type { PackageFile, ProjectSummary } from '@/features/projects/types'
import { apiUrl, errorMessage } from '@/lib/api'
import { cn } from '@/lib/utils'

const FILE_ICON = { pdf: FileText, docx: FileType2, xlsx: FileSpreadsheet } as const
const SEVERITY = {
  high: 'border-status-gap/60 text-status-gap',
  medium: 'border-status-partial/60 text-status-partial',
  low: 'border-border text-muted-foreground',
} as const

function OutlineCard({ projectId }: { projectId: number }) {
  const outline = useOutline(projectId)
  const generate = useGenerateOutline(projectId)
  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-3">
        <div>
          <CardTitle>Proposal outline</CardTitle>
          <CardDescription>
            Sections follow the scoring criteria; pages are budgeted by marks.
          </CardDescription>
        </div>
        <Button
          variant="outline"
          size="sm"
          disabled={generate.isPending}
          onClick={() =>
            generate.mutate(undefined, { onError: (e) => toast.error(errorMessage(e)) })
          }
        >
          <ListChecks aria-hidden="true" /> {outline.data?.length ? 'Rebuild' : 'Build outline'}
        </Button>
      </CardHeader>
      <CardContent>
        {outline.isPending ? (
          <LoadingRows rows={3} />
        ) : outline.data?.length ? (
          <ul className="flex flex-col gap-3">
            {outline.data.map((section) => {
              const over = section.estimated_pages > section.page_budget
              const share = section.page_budget
                ? Math.min(100, (section.estimated_pages / section.page_budget) * 100)
                : 0
              return (
                <li key={section.id} className="flex flex-col gap-1">
                  <div className="flex justify-between gap-2 text-sm">
                    <span>
                      {section.order + 1}. {section.title}
                      {section.requirement_count ? (
                        <span className="text-xs text-muted-foreground">
                          {' '}
                          · {section.requirement_count} answers
                        </span>
                      ) : null}
                    </span>
                    <span
                      className={cn(
                        'text-xs tabular-nums',
                        over ? 'font-semibold text-status-gap' : 'text-muted-foreground',
                      )}
                    >
                      {section.estimated_pages} / {section.page_budget} pages
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-muted" aria-hidden="true">
                    <div
                      className={cn('h-1.5 rounded-full', over ? 'bg-status-gap' : 'bg-primary')}
                      style={{ width: `${share}%` }}
                    />
                  </div>
                </li>
              )
            })}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">
            Build the outline to see page budgets per section.
          </p>
        )}
      </CardContent>
    </Card>
  )
}

function ConsistencyCard({ projectId }: { projectId: number }) {
  const conflicts = useConflicts(projectId)
  const run = useRunConsistency(projectId)
  const resolve = useResolveConflict(projectId)
  const open = (conflicts.data ?? []).filter((c) => !c.resolved)
  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-3">
        <div>
          <CardTitle>Consistency check</CardTitle>
          <CardDescription>
            Finds answers that contradict each other (team size, SLA hours, experience).
          </CardDescription>
        </div>
        <Button
          variant="outline"
          size="sm"
          disabled={run.isPending}
          onClick={() =>
            run.mutate(undefined, {
              onSuccess: (result) =>
                toast.success(
                  result.length ? `${result.length} conflict(s) found` : 'No conflicts found',
                ),
              onError: (e) => toast.error(errorMessage(e)),
            })
          }
        >
          <Scale aria-hidden="true" /> {run.isPending ? 'Checking…' : 'Run check'}
        </Button>
      </CardHeader>
      <CardContent>
        {open.length === 0 ? (
          <p className="text-sm text-muted-foreground">No open conflicts.</p>
        ) : (
          <ul className="flex flex-col gap-3">
            {open.map((conflict) => (
              <li
                key={conflict.id}
                className="rounded-md border border-status-partial/60 p-3 text-sm"
              >
                <div className="mb-1 flex items-center justify-between gap-2">
                  <span className="font-medium capitalize">
                    {conflict.key.replaceAll('_', ' ')}
                  </span>
                  <Button size="xs" variant="ghost" onClick={() => resolve.mutate(conflict.id)}>
                    Mark resolved
                  </Button>
                </div>
                <ul className="flex flex-col gap-1 text-xs">
                  {conflict.values.map((entry) => {
                    const value = String(entry.value)
                    const rows = (entry.rows ?? []) as {
                      requirement_id: number
                      req_code: string
                    }[]
                    return (
                      <li key={value}>
                        <span className="font-semibold">{value}</span> in{' '}
                        {rows.map((r, index) => (
                          <span key={r.requirement_id}>
                            {index ? ', ' : ''}
                            <Link
                              className="text-primary hover:underline"
                              to={`/projects/${projectId}/matrix?row=${r.requirement_id}`}
                            >
                              {r.req_code}
                            </Link>
                          </span>
                        ))}
                      </li>
                    )
                  })}
                </ul>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

function FileRow({ projectId, file }: { projectId: number; file: PackageFile }) {
  const Icon = FILE_ICON[file.format]
  return (
    <li className="flex items-center gap-3 rounded-md border border-border px-3 py-2 text-sm">
      <Icon aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />
      <div className="min-w-0 flex-1">
        <a
          className="block truncate font-medium hover:underline"
          href={apiUrl(`/projects/${projectId}/package/files/${encodeURIComponent(file.name)}`)}
          target="_blank"
          rel="noreferrer"
        >
          {file.name}
        </a>
        <span className="text-xs text-muted-foreground">
          {file.label}
          {file.pages ? ` · ${file.pages} page${file.pages === 1 ? '' : 's'}` : ''}
        </span>
      </div>
      <Badge variant="outline" className="uppercase">
        {file.format}
      </Badge>
    </li>
  )
}

export function PackageTab({ project }: { project: ProjectSummary }) {
  const validation = useValidation(project.id)
  const info = usePackageInfo(project.id)
  const start = useStartJob((id) => `/projects/${id}/package`)
  const invalidate = useInvalidateProject()
  const [jobId, setJobId] = useState<number | null>(null)
  const [confirmOpen, setConfirmOpen] = useState(false)

  const generate = () =>
    start.mutate(project.id, {
      onSuccess: (r) => setJobId(r.job_id),
      onError: (e) => toast.error(errorMessage(e)),
    })
  const blockers = validation.data?.blockers ?? []

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card className="lg:col-span-2">
        <CardHeader className="flex flex-row items-center gap-4">
          {validation.data ? (
            <ScoreRing value={validation.data.readiness_score} label="Readiness" size={84} />
          ) : null}
          <div className="flex-1">
            <CardTitle>Readiness</CardTitle>
            <CardDescription>
              {validation.data
                ? `${validation.data.counts.approved} of ${validation.data.counts.requirements} answers approved · technical proposal about ${validation.data.estimated_pages} pages${validation.data.page_limit ? ` of ${validation.data.page_limit} allowed` : ''}`
                : 'Checking…'}
            </CardDescription>
          </div>
          <Button
            disabled={start.isPending || jobId !== null}
            onClick={() => (blockers.length ? setConfirmOpen(true) : generate())}
          >
            <Package aria-hidden="true" /> Generate package
          </Button>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {validation.isPending ? (
            <LoadingRows rows={3} />
          ) : validation.error ? (
            <ErrorState
              message={errorMessage(validation.error)}
              onRetry={() => void validation.refetch()}
            />
          ) : blockers.length === 0 ? (
            <p className="text-sm text-status-full">
              No blockers. The package is ready to sign and upload.
            </p>
          ) : (
            <ul className="flex flex-col gap-2">
              {blockers.map((blocker, index) => (
                <li
                  key={index}
                  className={cn(
                    'flex items-center gap-2 rounded-md border px-3 py-2 text-sm',
                    SEVERITY[blocker.severity],
                  )}
                >
                  <span className="text-xs font-semibold uppercase">{blocker.severity}</span>
                  <span className="flex-1 text-foreground">{blocker.message}</span>
                  {blocker.requirement_ids?.length ? (
                    <Link
                      className="text-xs text-primary hover:underline"
                      to={`/projects/${project.id}/matrix?${blocker.code === 'mandatory_gaps' ? 'status=gap&mandatory=1' : blocker.code === 'unapproved' ? 'mandatory=1' : 'changed=1'}`}
                    >
                      Fix in matrix
                    </Link>
                  ) : blocker.code === 'eligibility' || blocker.code === 'form_fields' ? (
                    <Link className="text-xs text-primary hover:underline" to="/company">
                      Update profile
                    </Link>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
          {jobId ? (
            <JobProgress
              jobId={jobId}
              onRetry={setJobId}
              onDone={(job) => {
                invalidate(project.id)
                setJobId(null)
                if (job.status === 'succeeded') toast.success('Package generated')
              }}
            />
          ) : null}
        </CardContent>
      </Card>

      <Card className="lg:col-span-2">
        <CardHeader className="flex flex-row items-start justify-between gap-3">
          <div>
            <CardTitle>Bid package</CardTitle>
            <CardDescription>
              Named and formatted as the RFP requires. Prices, signatures and the upload stay with
              you.
            </CardDescription>
          </div>
          {info.data?.zip_name ? (
            <Button asChild>
              <a href={apiUrl(`/projects/${project.id}/package/download`)}>
                <Download aria-hidden="true" /> Download ZIP
              </a>
            </Button>
          ) : null}
        </CardHeader>
        <CardContent>
          {info.isPending ? (
            <LoadingRows rows={3} />
          ) : info.data?.files.length ? (
            <ul className="grid gap-2 md:grid-cols-2">
              {info.data.files.map((file) => (
                <FileRow key={file.name} projectId={project.id} file={file} />
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">Generate the package to see its files.</p>
          )}
        </CardContent>
      </Card>

      <OutlineCard projectId={project.id} />
      <ConsistencyCard projectId={project.id} />

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Generate with {blockers.length} open blocker(s)?</AlertDialogTitle>
            <AlertDialogDescription>
              You can generate a draft package now and regenerate it after fixing the blockers. Do
              not submit a package with open high-severity blockers.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={generate}>Generate anyway</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
