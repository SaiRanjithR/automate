import { FileDiff } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { toast } from 'sonner'

import { Dropzone } from '@/components/common/Dropzone'
import { EmptyState } from '@/components/common/EmptyState'
import { LoadingRows } from '@/components/common/LoadingRows'
import { StatusChip, type ComplianceStatus } from '@/components/common/StatusChip'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { jobCount } from '@/features/jobs/api'
import { JobProgress } from '@/features/jobs/JobProgress'
import { DiffView } from '@/features/matrix/DiffView'
import { useInvalidateProject, useRequirements, useUploadAddendum } from '@/features/projects/api'
import type { ProjectSummary } from '@/features/projects/types'
import { errorMessage } from '@/lib/api'

const LABEL = {
  modified: { text: 'Modified', className: 'border-status-custom/50 text-status-custom' },
  added: { text: 'New', className: 'border-status-full/50 text-status-full' },
  removed: { text: 'Removed', className: 'border-status-gap/50 text-status-gap' },
} as const

export function AddendaTab({ project }: { project: ProjectSummary }) {
  const upload = useUploadAddendum(project.id)
  const invalidate = useInvalidateProject()
  const [jobId, setJobId] = useState<number | null>(null)
  const changes = useRequirements(project.id, { version_status: 'modified,added,removed' })
  const addenda = project.files.filter((f) => f.role === 'addendum')

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Upload an addendum or corrigendum</CardTitle>
          <CardDescription>
            BidReady finds changed, new and deleted clauses, updates the deadline, and re-drafts
            only the affected rows. Approved answers on changed rows go back to review.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {jobId ? (
            <JobProgress
              jobId={jobId}
              onRetry={setJobId}
              onDone={(job) => {
                invalidate(project.id)
                if (job.status === 'succeeded') {
                  toast.success(
                    `${jobCount(job, 'modified')} modified, ${jobCount(job, 'added')} new, ${jobCount(job, 'removed')} removed`,
                  )
                }
                setJobId(null)
              }}
            />
          ) : (
            <Dropzone
              label={upload.isPending ? 'Uploading…' : 'Drop the addendum here'}
              disabled={upload.isPending}
              onFiles={(files) => {
                const file = files[0]
                if (!file) return
                upload.mutate(file, {
                  onSuccess: (r) => setJobId(r.job_id),
                  onError: (e) => toast.error(errorMessage(e)),
                })
              }}
            />
          )}
          {addenda.length ? (
            <p className="text-xs text-muted-foreground">
              Applied: {addenda.map((f) => String(f.filename)).join(', ')}
            </p>
          ) : null}
        </CardContent>
      </Card>
      {changes.isPending ? (
        <LoadingRows rows={3} />
      ) : (changes.data?.items.length ?? 0) === 0 ? (
        <EmptyState
          icon={FileDiff}
          title="No changes yet"
          description="Changes from uploaded addenda will appear here."
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {changes.data?.items.map((row) => {
            const label = LABEL[row.version_status as keyof typeof LABEL]
            return (
              <li key={row.id} className="flex flex-col gap-2 rounded-lg border border-border p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-sm font-semibold">{row.req_code}</span>
                  {label ? (
                    <Badge variant="outline" className={label.className}>
                      {label.text}
                    </Badge>
                  ) : null}
                  <StatusChip status={(row.response?.status ?? 'pending') as ComplianceStatus} />
                  <span className="text-xs text-muted-foreground">{row.section_path}</span>
                  {row.version_status !== 'removed' ? (
                    <Link
                      className="ml-auto text-sm text-primary hover:underline"
                      to={`/projects/${project.id}/matrix?row=${row.id}`}
                    >
                      Open in matrix
                    </Link>
                  ) : null}
                </div>
                {row.version_status === 'modified' ? (
                  <DiffView requirementId={row.id} />
                ) : (
                  <p
                    className={
                      row.version_status === 'removed'
                        ? 'text-sm text-muted-foreground line-through'
                        : 'text-sm'
                    }
                  >
                    {row.text}
                  </p>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
