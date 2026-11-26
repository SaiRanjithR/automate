import { CalendarClock, FileText, Trash2 } from 'lucide-react'
import { Link } from 'react-router'
import { toast } from 'sonner'

import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingRows } from '@/components/common/LoadingRows'
import { PageHeader } from '@/components/common/PageHeader'
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
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useDeleteProject, useProjects } from '@/features/projects/api'
import type { ProjectSummary } from '@/features/projects/types'
import { errorMessage } from '@/lib/api'
import { daysUntil, deadlineLabel } from '@/lib/format'
import { cn } from '@/lib/utils'

const DECISION: Record<string, { label: string; className: string }> = {
  go: { label: 'Go', className: 'border-status-full/50 text-status-full' },
  review: { label: 'Review', className: 'border-status-partial/50 text-status-partial' },
  no_go: { label: 'No-go', className: 'border-status-gap/50 text-status-gap' },
}

function ProjectCard({ project }: { project: ProjectSummary }) {
  const remove = useDeleteProject()
  const days = daysUntil(project.deadline)
  const decision = project.go_no_go?.decision as string | undefined
  return (
    <Card className="flex flex-col">
      <CardHeader className="flex flex-row items-start justify-between gap-3">
        <div className="min-w-0">
          <CardTitle className="line-clamp-2 text-base leading-snug">
            <Link to={`/projects/${project.id}/matrix`} className="hover:underline">
              {project.title || `Project ${project.id}`}
            </Link>
          </CardTitle>
          <p className="mt-1 truncate text-xs text-muted-foreground">
            {project.tender_no || 'No tender number'} · {project.buyer || 'Buyer not found'}
          </p>
        </div>
        <ScoreRing value={project.readiness_score} label="Readiness" size={56} />
      </CardHeader>
      <CardContent className="mt-auto flex flex-wrap items-center gap-2 text-xs">
        <span
          className={cn(
            'inline-flex items-center gap-1',
            days !== null && days < 7 && 'font-medium text-status-gap',
          )}
        >
          <CalendarClock aria-hidden="true" className="size-3.5" />
          {deadlineLabel(project.deadline)}
        </span>
        <Badge variant="outline">{project.counts.requirements ?? 0} requirements</Badge>
        {project.counts.gaps ? (
          <Badge variant="outline" className="border-status-gap/50 text-status-gap">
            {project.counts.gaps} gaps
          </Badge>
        ) : null}
        <Badge variant="outline">{project.counts.approved ?? 0} approved</Badge>
        {decision && DECISION[decision] ? (
          <Badge variant="outline" className={DECISION[decision].className}>
            {DECISION[decision].label}
          </Badge>
        ) : null}
        {project.outcome !== 'unknown' ? (
          <Badge variant="secondary">{project.outcome === 'won' ? 'Won' : 'Lost'}</Badge>
        ) : null}
        {project.status === 'analysing' ? <Badge variant="secondary">Analysing…</Badge> : null}
        {project.status === 'failed' ? <Badge variant="destructive">Analysis failed</Badge> : null}
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button
              variant="ghost"
              size="icon-sm"
              className="ml-auto"
              aria-label={`Delete ${project.title || 'project'}`}
            >
              <Trash2 />
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete this project?</AlertDialogTitle>
              <AlertDialogDescription>
                Its requirements, drafted answers and generated package will be removed. This cannot
                be undone.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={() =>
                  remove.mutate(project.id, {
                    onSuccess: () => toast.success('Project deleted'),
                    onError: (e) => toast.error(errorMessage(e)),
                  })
                }
              >
                Delete
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </CardContent>
    </Card>
  )
}

export function DashboardPage() {
  const { data, isPending, error, refetch } = useProjects()
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Dashboard"
        description="All your bids at a glance."
        action={
          <Button asChild>
            <Link to="/projects/new">New project</Link>
          </Button>
        }
      />
      {isPending ? (
        <LoadingRows rows={3} />
      ) : error ? (
        <ErrorState message={errorMessage(error)} onRetry={() => void refetch()} />
      ) : data.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="Upload your first tender"
          description="Add an RFP and BidReady will extract every requirement, rule and scoring criterion."
          action={
            <Button asChild variant="outline">
              <Link to="/projects/new">Start a project</Link>
            </Button>
          }
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {data.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </div>
      )}
    </div>
  )
}
