import { Sparkles } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { JobProgress } from '@/features/jobs/JobProgress'
import { useInvalidateProject, useStartJob } from '@/features/projects/api'
import { errorMessage } from '@/lib/api'

type DraftCardProps = { projectId: number; drafted: number; total: number; compact?: boolean }

/** Starts the "draft all answers" job and shows its progress. */
export function DraftAllButton({
  projectId,
  onStarted,
}: {
  projectId: number
  onStarted: (jobId: number) => void
}) {
  const start = useStartJob((id) => `/projects/${id}/draft`)
  return (
    <Button
      disabled={start.isPending}
      onClick={() =>
        start.mutate(projectId, {
          onSuccess: (r) => onStarted(r.job_id),
          onError: (e) => toast.error(errorMessage(e)),
        })
      }
    >
      <Sparkles aria-hidden="true" />
      Draft all answers
    </Button>
  )
}

export function DraftCard({ projectId, drafted, total }: DraftCardProps) {
  const [jobId, setJobId] = useState<number | null>(null)
  const invalidate = useInvalidateProject()
  return (
    <Card className="border-primary/40 bg-primary/5">
      <CardHeader>
        <CardTitle>Draft answers</CardTitle>
        <CardDescription>
          {drafted === 0
            ? `Draft cited answers for all ${total} requirements from your knowledge base. Each answer is reviewed for compliance as it is written.`
            : `${drafted} of ${total} requirements drafted.`}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {jobId ? (
          <JobProgress
            jobId={jobId}
            onRetry={setJobId}
            onDone={(job) => {
              invalidate(projectId)
              if (job.status === 'succeeded') toast.success('Drafting finished')
            }}
          />
        ) : (
          <DraftAllButton projectId={projectId} onStarted={setJobId} />
        )}
      </CardContent>
    </Card>
  )
}
