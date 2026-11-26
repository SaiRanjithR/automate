import { CalendarClock } from 'lucide-react'
import { Navigate, useNavigate, useParams } from 'react-router'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingRows } from '@/components/common/LoadingRows'
import { ScoreRing } from '@/components/common/ScoreRing'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { AddendaTab } from '@/features/addenda/AddendaTab'
import { AuditTab } from '@/features/audit/AuditTab'
import { MatrixTab } from '@/features/matrix/MatrixTab'
import { OverviewTab } from '@/features/overview/OverviewTab'
import { PackageTab } from '@/features/package/PackageTab'
import { useProject } from '@/features/projects/api'
import { PROJECT_TABS, isProjectTab } from '@/features/projects/tabs'
import { RulesTab } from '@/features/rules/RulesTab'
import { errorMessage } from '@/lib/api'
import { daysUntil, deadlineLabel, formatDate } from '@/lib/format'
import { cn } from '@/lib/utils'

export function ProjectPage() {
  const { id, tab } = useParams()
  const navigate = useNavigate()
  const projectId = Number(id)
  const { data: project, isPending, error, refetch } = useProject(projectId)

  if (!id || Number.isNaN(projectId)) return <Navigate to="/dashboard" replace />
  if (!isProjectTab(tab)) return <Navigate to={`/projects/${id}/overview`} replace />
  if (isPending) return <LoadingRows rows={6} label="Loading project" />
  if (error) return <ErrorState message={errorMessage(error)} onRetry={() => void refetch()} />

  const days = daysUntil(project.deadline)
  return (
    <div className="flex flex-col gap-5">
      <header className="flex items-start justify-between gap-4 border-b border-border pb-4">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold tracking-tight">
            {project.title || `Project ${project.id}`}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {project.tender_no || 'No tender number'} · {project.buyer || 'Buyer not found'}
          </p>
          <p
            className={cn(
              'mt-1 inline-flex items-center gap-1 text-sm',
              days !== null && days < 7 ? 'font-medium text-status-gap' : 'text-muted-foreground',
            )}
          >
            <CalendarClock aria-hidden="true" className="size-4" />
            {formatDate(project.deadline)} · {deadlineLabel(project.deadline)}
          </p>
        </div>
        <ScoreRing value={project.readiness_score} label="Readiness" />
      </header>
      <Tabs value={tab} onValueChange={(next) => void navigate(`/projects/${id}/${next}`)}>
        <TabsList>
          {PROJECT_TABS.map(({ value, label }) => (
            <TabsTrigger key={value} value={value}>
              {label}
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value="overview" className="pt-4">
          <OverviewTab project={project} />
        </TabsContent>
        <TabsContent value="matrix" className="pt-4">
          <MatrixTab project={project} />
        </TabsContent>
        <TabsContent value="rules" className="pt-4">
          <RulesTab projectId={project.id} />
        </TabsContent>
        <TabsContent value="addenda" className="pt-4">
          <AddendaTab project={project} />
        </TabsContent>
        <TabsContent value="audit" className="pt-4">
          <AuditTab project={project} />
        </TabsContent>
        <TabsContent value="package" className="pt-4">
          <PackageTab project={project} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
