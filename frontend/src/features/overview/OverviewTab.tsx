import { CheckCircle2, CircleAlert, XCircle } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { toast } from 'sonner'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingRows } from '@/components/common/LoadingRows'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useKnowledge } from '@/features/company/api'
import { DraftCard } from '@/features/overview/DraftCard'
import {
  useCriteria,
  useGoNoGo,
  useRules,
  useSaveWinThemes,
  useSetCompetition,
  useSetOutcome,
  useWinThemes,
} from '@/features/projects/api'
import type { GoNoGo, ProjectSummary } from '@/features/projects/types'
import { errorMessage } from '@/lib/api'
import { formatDate, inr } from '@/lib/format'
import { cn } from '@/lib/utils'

const DECISIONS = {
  go: { label: 'Go', icon: CheckCircle2, className: 'text-status-full' },
  review: { label: 'Review before bidding', icon: CircleAlert, className: 'text-status-partial' },
  no_go: { label: 'No-go', icon: XCircle, className: 'text-status-gap' },
} as const
const FACTORS: { key: keyof GoNoGo['factors']; label: string }[] = [
  { key: 'fit', label: 'Fit (evidence coverage)' },
  { key: 'risk', label: 'Requirement risk' },
  { key: 'resources', label: 'Time and resources' },
  { key: 'competition', label: 'Competition' },
]

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium">{value}</dd>
    </div>
  )
}

function GoNoGoCard({ project }: { project: ProjectSummary }) {
  const { data, isPending, error, refetch } = useGoNoGo(project.id)
  const setCompetition = useSetCompetition(project.id)
  if (isPending) return <LoadingRows rows={3} />
  if (error) return <ErrorState message={errorMessage(error)} onRetry={() => void refetch()} />
  const decision = DECISIONS[data.decision]
  return (
    <Card>
      <CardHeader>
        <CardTitle>Go / no-go</CardTitle>
        <CardDescription>
          {data.drafted
            ? 'Based on drafted answers, eligibility, time left and competition.'
            : 'Draft answers first for an accurate fit score.'}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className={cn('flex items-center gap-2 text-lg font-semibold', decision.className)}>
          <decision.icon aria-hidden="true" className="size-5" />
          {decision.label}
          <span className="ml-auto text-sm font-normal text-muted-foreground tabular-nums">
            Score {Math.round(data.score * 100)} / 100
          </span>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {FACTORS.map(({ key, label }) => (
            <div key={key} className="flex flex-col gap-1">
              <div className="flex justify-between text-xs">
                <span>{label}</span>
                <span className="text-muted-foreground tabular-nums">
                  {Math.round(data.factors[key] * 100)}%
                </span>
              </div>
              <Progress value={data.factors[key] * 100} aria-label={label} />
            </div>
          ))}
        </div>
        <ul className="flex list-disc flex-col gap-1 pl-5 text-sm">
          {data.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
        <div className="flex max-w-xs flex-col gap-1.5">
          <Label htmlFor="competition">How strong is the competition?</Label>
          <Select
            value={project.competition_rating ? String(project.competition_rating) : undefined}
            onValueChange={(value) =>
              setCompetition.mutate(Number(value), { onError: (e) => toast.error(errorMessage(e)) })
            }
          >
            <SelectTrigger id="competition">
              <SelectValue placeholder="Rate 1 (weak) to 5 (very strong)" />
            </SelectTrigger>
            <SelectContent>
              {['1 - Weak', '2 - Some', '3 - Moderate', '4 - Strong', '5 - Very strong'].map(
                (label, index) => (
                  <SelectItem key={label} value={String(index + 1)}>
                    {label}
                  </SelectItem>
                ),
              )}
            </SelectContent>
          </Select>
        </div>
      </CardContent>
    </Card>
  )
}

function WinThemesCard({ projectId }: { projectId: number }) {
  const { data } = useWinThemes(projectId)
  if (!data) return <LoadingRows rows={2} />
  return <WinThemesEditor key={data.join('|')} projectId={projectId} initial={data} />
}

function WinThemesEditor({ projectId, initial }: { projectId: number; initial: string[] }) {
  const save = useSaveWinThemes(projectId)
  const [themes, setThemes] = useState(() => [0, 1, 2].map((i) => initial[i] ?? ''))
  return (
    <Card>
      <CardHeader>
        <CardTitle>Win themes</CardTitle>
        <CardDescription>
          Up to 3 reasons the buyer should pick you. Used in the executive summary and drafts.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {themes.map((theme, index) => (
          <Input
            key={index}
            aria-label={`Win theme ${index + 1}`}
            placeholder={`Win theme ${index + 1}`}
            value={theme}
            onChange={(event) =>
              setThemes(themes.map((t, i) => (i === index ? event.target.value : t)))
            }
          />
        ))}
        <Button
          variant="outline"
          className="self-start"
          disabled={save.isPending}
          onClick={() =>
            save.mutate(themes, {
              onSuccess: () => toast.success('Win themes saved'),
              onError: (e) => toast.error(errorMessage(e)),
            })
          }
        >
          Save themes
        </Button>
      </CardContent>
    </Card>
  )
}

export function OverviewTab({ project }: { project: ProjectSummary }) {
  const rules = useRules(project.id)
  const criteria = useCriteria(project.id)
  const outcome = useSetOutcome(project.id)
  const knowledge = useKnowledge(false)
  const knowledgeEmpty =
    knowledge.data !== undefined && knowledge.data.filter((d) => d.status === 'ready').length === 0
  const counts = project.counts
  const totalMarks = (criteria.data ?? []).reduce((sum, c) => sum + (c.max_marks ?? 0), 0)

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {project.status === 'failed' ? (
        <div className="lg:col-span-2">
          <ErrorState
            title="Analysis failed"
            message={project.latest_job?.error ?? 'Try analysing again.'}
          />
        </div>
      ) : null}
      {knowledgeEmpty ? (
        <Alert variant="destructive" className="lg:col-span-2">
          <AlertTitle>Your knowledge base is empty</AlertTitle>
          <AlertDescription>
            Every answer needs evidence from your documents, so drafting now would mark every row as
            a gap.{' '}
            <Link to="/knowledge" className="underline">
              Upload past proposals or a company profile
            </Link>{' '}
            first.
          </AlertDescription>
        </Alert>
      ) : null}
      {counts.drafted === 0 && (counts.requirements ?? 0) > 0 ? (
        <div className="lg:col-span-2">
          <DraftCard
            projectId={project.id}
            drafted={counts.drafted ?? 0}
            total={counts.requirements ?? 0}
          />
        </div>
      ) : null}
      <Card>
        <CardHeader>
          <CardTitle>Key facts</CardTitle>
        </CardHeader>
        <CardContent>
          {rules.isPending ? (
            <LoadingRows rows={3} />
          ) : (
            <dl className="grid grid-cols-2 gap-4">
              <Fact label="Deadline" value={formatDate(project.deadline)} />
              <Fact label="Portal" value={rules.data?.portal ?? 'Not stated'} />
              <Fact
                label="Bid system"
                value={(rules.data?.bid_system ?? 'Not stated').replace('_', ' ')}
              />
              <Fact label="EMD" value={inr(rules.data?.emd?.amount_inr)} />
              <Fact
                label="Page limit"
                value={
                  rules.data?.format?.page_limit
                    ? `${rules.data.format.page_limit} pages`
                    : 'Not stated'
                }
              />
              <Fact
                label="Evaluation"
                value={rules.data?.qcbs_split ? `QCBS ${rules.data.qcbs_split}` : 'Not stated'}
              />
              <Fact
                label="Requirements"
                value={`${counts.requirements ?? 0} (${counts.mandatory ?? 0} mandatory)`}
              />
              <Fact
                label="Approved"
                value={`${counts.approved ?? 0} of ${counts.requirements ?? 0}`}
              />
            </dl>
          )}
          <div className="mt-4 flex flex-wrap gap-2">
            <Button asChild size="sm">
              <Link to={`/projects/${project.id}/matrix`}>Open compliance matrix</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link to={`/projects/${project.id}/rules`}>Submission rules</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
      <GoNoGoCard project={project} />
      <Card>
        <CardHeader>
          <CardTitle>How bids are scored</CardTitle>
          <CardDescription>
            {rules.data?.min_qualifying_marks
              ? `Minimum qualifying technical score: ${rules.data.min_qualifying_marks}. `
              : ''}
            Each requirement is linked to the criterion it is scored under.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {criteria.isPending ? (
            <LoadingRows rows={3} />
          ) : criteria.data?.length ? (
            <ul className="flex flex-col gap-3">
              {criteria.data.map((c) => (
                <li key={c.id} className="flex flex-col gap-1">
                  <div className="flex items-center justify-between gap-2 text-sm">
                    <Link
                      className="font-medium hover:underline"
                      to={`/projects/${project.id}/matrix?criterion=${c.id}`}
                    >
                      {c.name}
                    </Link>
                    <span className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Badge variant="outline">{c.requirement_count} rows</Badge>
                      <span className="tabular-nums">{c.max_marks ?? '—'} marks</span>
                    </span>
                  </div>
                  <Progress
                    value={totalMarks ? ((c.max_marks ?? 0) / totalMarks) * 100 : 0}
                    aria-label={`${c.name} weight`}
                  />
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">No scoring criteria found in the RFP.</p>
          )}
        </CardContent>
      </Card>
      <div className="flex flex-col gap-4">
        <WinThemesCard projectId={project.id} />
        <Card>
          <CardHeader>
            <CardTitle>Bid outcome</CardTitle>
            <CardDescription>
              Answers from won bids are preferred when drafting future bids.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Select
              value={project.outcome}
              onValueChange={(value) =>
                outcome.mutate(value as 'unknown' | 'won' | 'lost', {
                  onSuccess: () => toast.success('Outcome saved'),
                })
              }
            >
              <SelectTrigger aria-label="Bid outcome" className="max-w-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="unknown">Not decided yet</SelectItem>
                <SelectItem value="won">Won</SelectItem>
                <SelectItem value="lost">Lost</SelectItem>
              </SelectContent>
            </Select>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
