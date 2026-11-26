import { RefreshCw, ShieldAlert, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { toast } from 'sonner'

import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingRows } from '@/components/common/LoadingRows'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { useAudit, useRerunAudit } from '@/features/policies/api'
import { SeverityBadge } from '@/features/policies/SeverityBadge'
import type { ProjectSummary } from '@/features/projects/types'
import { errorMessage } from '@/lib/api'
import { cn } from '@/lib/utils'

export function AuditTab({ project }: { project: ProjectSummary }) {
  const audit = useAudit(project.id)
  const rerun = useRerunAudit(project.id)
  const [onlyNew, setOnlyNew] = useState(false)
  const run = audit.data
  const findings = (run?.findings ?? []).filter((f) => !onlyNew || f.new)

  const start = () =>
    rerun.mutate(undefined, {
      onSuccess: (result) =>
        toast.success(
          result.new_count
            ? `${result.new_count} new exception(s) found`
            : `Audit complete: ${result.findings.length} exception(s), nothing new`,
        ),
      onError: (e) => toast.error(errorMessage(e)),
    })

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2">
              <ShieldAlert aria-hidden="true" className="size-4" /> Policy audit
            </CardTitle>
            <CardDescription>
              Checks every requirement, answer and tender fact against your{' '}
              <Link to="/policies" className="text-primary underline">
                policy rules
              </Link>
              . Change a rule, then re-run: new exceptions are highlighted.
            </CardDescription>
          </div>
          <Button onClick={start} disabled={rerun.isPending}>
            <RefreshCw aria-hidden="true" className={cn(rerun.isPending && 'animate-spin')} />
            {run ? 'Re-run audit' : 'Run audit'}
          </Button>
        </CardHeader>
        {run ? (
          <CardContent className="flex flex-wrap items-center gap-3 text-sm">
            <Badge variant="outline">{run.rules_evaluated} rules checked</Badge>
            <SeverityBadge severity="high" className="gap-1.5" />
            <span className="tabular-nums">{run.counts.high}</span>
            <SeverityBadge severity="medium" />
            <span className="tabular-nums">{run.counts.medium}</span>
            <SeverityBadge severity="low" />
            <span className="tabular-nums">{run.counts.low}</span>
            <span
              className={cn(
                'inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-semibold',
                run.new_count
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-muted-foreground',
              )}
            >
              <Sparkles aria-hidden="true" className="size-3" /> {run.new_count} new
            </span>
            {run.resolved ? (
              <span className="text-xs text-status-full">
                {run.resolved} resolved since last run
              </span>
            ) : null}
            <span className="ml-auto text-xs text-muted-foreground">
              Last run {new Date(run.created_at).toLocaleString('en-IN')}
            </span>
          </CardContent>
        ) : null}
      </Card>

      {run?.errors.length ? (
        <Alert variant="destructive">
          <AlertTitle>Some rules could not be checked</AlertTitle>
          <AlertDescription>
            <ul className="list-disc pl-4">
              {run.errors.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      ) : null}

      {audit.isPending ? (
        <LoadingRows rows={4} />
      ) : audit.error ? (
        <ErrorState message={errorMessage(audit.error)} onRetry={() => void audit.refetch()} />
      ) : !run ? (
        <EmptyState
          icon={ShieldAlert}
          title="No audit yet"
          description="Run the audit to check this bid against your business, financial and compliance rules."
          action={<Button onClick={start}>Run audit</Button>}
        />
      ) : (
        <>
          <div className="flex items-center gap-2">
            <Switch id="only-new" checked={onlyNew} onCheckedChange={setOnlyNew} />
            <Label htmlFor="only-new" className="text-sm">
              Only new exceptions
            </Label>
          </div>
          {findings.length === 0 ? (
            <p className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
              {onlyNew
                ? 'Nothing new since the last run.'
                : 'No exceptions: this bid follows every active rule.'}
            </p>
          ) : (
            <ul className="flex flex-col gap-2">
              {findings.map((finding) => (
                <li
                  key={finding.key}
                  className={cn(
                    'flex flex-wrap items-center gap-3 rounded-lg border border-border px-4 py-3 text-sm',
                    finding.new &&
                      'border-primary/60 bg-primary/5 shadow-[inset_3px_0_0_var(--primary)]',
                  )}
                >
                  {finding.new ? (
                    <span className="inline-flex animate-pulse items-center gap-1 rounded-md bg-primary px-2 py-0.5 text-xs font-semibold text-primary-foreground motion-reduce:animate-none">
                      <Sparkles aria-hidden="true" className="size-3" /> NEW
                    </span>
                  ) : null}
                  <SeverityBadge severity={finding.severity} />
                  <span className="min-w-0 flex-1">
                    <span className="block">{finding.message}</span>
                    <span className="block text-xs text-muted-foreground">
                      {finding.rule_name} ·{' '}
                      {finding.source === 'ui'
                        ? 'rule from the app'
                        : finding.source.replace('file:', 'from ')}
                    </span>
                  </span>
                  {finding.target ? (
                    <Link
                      className="font-mono text-xs text-primary hover:underline"
                      to={`/projects/${project.id}/matrix?row=${finding.target.requirement_id}`}
                    >
                      {finding.target.req_code}
                    </Link>
                  ) : (
                    <Badge variant="outline">Tender</Badge>
                  )}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  )
}
