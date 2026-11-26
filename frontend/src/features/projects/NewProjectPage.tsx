import { FileText, X } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'

import { Dropzone } from '@/components/common/Dropzone'
import { PageHeader } from '@/components/common/PageHeader'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { jobCount } from '@/features/jobs/api'
import { JobProgress } from '@/features/jobs/JobProgress'
import { useCreateProject, useInvalidateProject } from '@/features/projects/api'
import { ANALYSE_STEPS } from '@/features/projects/steps'
import { errorMessage } from '@/lib/api'

function FileChip({ file, onRemove }: { file: File; onRemove: () => void }) {
  return (
    <li className="flex items-center gap-2 rounded-md border border-border px-3 py-2 text-sm">
      <FileText aria-hidden="true" className="size-4 text-muted-foreground" />
      <span className="truncate">{file.name}</span>
      <span className="ml-auto text-xs text-muted-foreground">
        {(file.size / 1024 / 1024).toFixed(1)} MB
      </span>
      <Button variant="ghost" size="icon-xs" aria-label={`Remove ${file.name}`} onClick={onRemove}>
        <X />
      </Button>
    </li>
  )
}

export function NewProjectPage() {
  const [main, setMain] = useState<File | null>(null)
  const [attachments, setAttachments] = useState<File[]>([])
  const [title, setTitle] = useState('')
  const [job, setJob] = useState<{ jobId: number; projectId: number } | null>(null)
  const create = useCreateProject()
  const navigate = useNavigate()
  const invalidate = useInvalidateProject()

  const start = () => {
    if (!main) return
    create.mutate(
      { main, attachments, title },
      {
        onSuccess: (result) => setJob({ jobId: result.job_id, projectId: result.project_id ?? 0 }),
        onError: (e) => toast.error(errorMessage(e)),
      },
    )
  }

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <PageHeader
        title="New project"
        description="Upload the RFP with its attachments. BidReady reads every page and builds the compliance matrix."
      />
      {job ? (
        <Card>
          <CardHeader>
            <CardTitle>Analysing {main?.name}</CardTitle>
            <CardDescription>This usually takes under a minute.</CardDescription>
          </CardHeader>
          <CardContent>
            <JobProgress
              jobId={job.jobId}
              steps={ANALYSE_STEPS}
              onRetry={(jobId) => setJob({ ...job, jobId })}
              onDone={(result) => {
                invalidate(job.projectId)
                if (result.status === 'succeeded') {
                  toast.success(`Found ${jobCount(result, 'requirements')} requirements`)
                  void navigate(`/projects/${job.projectId}/overview`)
                }
              }}
            />
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="flex flex-col gap-5 pt-6">
            <div className="flex flex-col gap-2">
              <Label>Main RFP document</Label>
              {main ? (
                <ul>
                  <FileChip file={main} onRemove={() => setMain(null)} />
                </ul>
              ) : (
                <Dropzone
                  label="Drop the RFP here or click to choose"
                  onFiles={(files) => setMain(files[0] ?? null)}
                />
              )}
            </div>
            <div className="flex flex-col gap-2">
              <Label>Attachments, annexures and exhibits (optional)</Label>
              {attachments.length ? (
                <ul className="flex flex-col gap-2">
                  {attachments.map((file, index) => (
                    <FileChip
                      key={`${file.name}-${index}`}
                      file={file}
                      onRemove={() => setAttachments(attachments.filter((_, i) => i !== index))}
                    />
                  ))}
                </ul>
              ) : null}
              <Dropzone
                label="Add attachments"
                multiple
                onFiles={(files) => setAttachments([...attachments, ...files])}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="title">Project name (optional)</Label>
              <Input
                id="title"
                placeholder="Taken from the RFP when left blank"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
              />
            </div>
            <Button className="self-start" disabled={!main || create.isPending} onClick={start}>
              {create.isPending ? 'Uploading…' : 'Upload and analyse'}
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
