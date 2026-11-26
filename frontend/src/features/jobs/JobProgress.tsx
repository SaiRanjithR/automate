import { CheckCircle2, Loader2, XCircle } from 'lucide-react'
import { useEffect, useRef } from 'react'

import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { isJobRunning, useJob } from '@/features/jobs/api'
import type { Job } from '@/features/projects/types'
import { api, errorMessage } from '@/lib/api'
import { cn } from '@/lib/utils'

export type JobStep = { stage: string; label: string }

type JobProgressProps = {
  jobId: number
  steps?: JobStep[]
  onDone?: (job: Job) => void
  onRetry?: (newJobId: number) => void
  className?: string
}

const COUNT_LABELS: Record<string, string> = {
  pages: 'pages',
  requirements: 'requirements',
  forms: 'forms',
  eligibility: 'eligibility criteria',
  criteria: 'scoring criteria',
  drafted: 'drafted',
  gaps: 'gaps',
  modified: 'modified',
  added: 'added',
  removed: 'removed',
  indexed: 'indexed',
  files: 'files',
}

export function JobProgress({ jobId, steps, onDone, onRetry, className }: JobProgressProps) {
  const { data: job, error } = useJob(jobId)
  const notified = useRef(false)

  useEffect(() => {
    if (job && !isJobRunning(job) && !notified.current) {
      notified.current = true
      onDone?.(job)
    }
  }, [job, onDone])

  if (error) return <p className="text-sm text-destructive">{errorMessage(error)}</p>
  if (!job) return null
  const running = isJobRunning(job)
  const stageIndex = steps?.findIndex((s) => s.stage === job.stage) ?? -1
  const counts = Object.entries(job.counts).filter(
    ([key, value]) => key in COUNT_LABELS && typeof value === 'number',
  )

  return (
    <div
      className={cn('flex flex-col gap-3 rounded-lg border border-border p-4', className)}
      aria-live="polite"
    >
      <div className="flex items-center gap-2 text-sm font-medium">
        {running ? (
          <Loader2 aria-hidden="true" className="size-4 animate-spin text-primary" />
        ) : job.status === 'succeeded' ? (
          <CheckCircle2 aria-hidden="true" className="size-4 text-status-full" />
        ) : (
          <XCircle aria-hidden="true" className="size-4 text-destructive" />
        )}
        <span>{job.status === 'failed' ? 'Failed' : job.message || 'Starting'}</span>
        <span className="ml-auto text-xs text-muted-foreground tabular-nums">{job.progress}%</span>
      </div>
      <Progress value={job.progress} aria-label="Progress" />
      {steps ? (
        <ol className="grid gap-1 text-sm sm:grid-cols-2">
          {steps.map((step, index) => {
            const done = job.status === 'succeeded' || index < stageIndex
            const active = running && index === stageIndex
            return (
              <li
                key={step.stage}
                className={cn(
                  'flex items-center gap-2',
                  !done && !active && 'text-muted-foreground',
                )}
              >
                {done ? (
                  <CheckCircle2 aria-hidden="true" className="size-3.5 text-status-full" />
                ) : active ? (
                  <Loader2 aria-hidden="true" className="size-3.5 animate-spin text-primary" />
                ) : (
                  <span aria-hidden="true" className="size-3.5 rounded-full border border-border" />
                )}
                {step.label}
              </li>
            )
          })}
        </ol>
      ) : null}
      {counts.length ? (
        <p className="text-xs text-muted-foreground">
          {counts.map(([key, value]) => `${String(value)} ${COUNT_LABELS[key] ?? key}`).join(' · ')}
        </p>
      ) : null}
      {job.status === 'failed' ? (
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm text-destructive">{job.error}</p>
          {onRetry ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                void api<{ job_id: number }>(`/jobs/${job.id}/retry`, { method: 'POST' }).then(
                  (r) => {
                    notified.current = false
                    onRetry(r.job_id)
                  },
                )
              }}
            >
              Retry
            </Button>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
