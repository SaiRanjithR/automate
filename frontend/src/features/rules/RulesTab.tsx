import { CheckCircle2, CircleAlert, CircleHelp } from 'lucide-react'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingRows } from '@/components/common/LoadingRows'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useRules } from '@/features/projects/api'
import type { EligibilityItem } from '@/features/projects/types'
import { errorMessage } from '@/lib/api'
import { formatDate, inr } from '@/lib/format'

const ELIGIBILITY = {
  met: { label: 'Ready', icon: CheckCircle2, className: 'text-status-full' },
  missing: { label: 'Missing', icon: CircleAlert, className: 'text-status-gap font-semibold' },
  manual: { label: 'Check', icon: CircleHelp, className: 'text-status-partial' },
} as const

function Row({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="grid grid-cols-[10rem_1fr] gap-3 border-b border-border py-2 text-sm last:border-0">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className={value ? '' : 'text-muted-foreground'}>{value || 'Not stated'}</dd>
    </div>
  )
}

function EligibilityStatus({ item }: { item: EligibilityItem }) {
  const style = ELIGIBILITY[item.status]
  return (
    <span className={`inline-flex items-center gap-1 text-xs ${style.className}`}>
      <style.icon aria-hidden="true" className="size-3.5" /> {style.label}
    </span>
  )
}

export function RulesTab({ projectId }: { projectId: number }) {
  const { data: rules, isPending, error, refetch } = useRules(projectId)
  if (isPending) return <LoadingRows rows={6} label="Loading submission rules" />
  if (error) return <ErrorState message={errorMessage(error)} onRetry={() => void refetch()} />
  const format = rules.format
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Where and when</CardTitle>
        </CardHeader>
        <CardContent>
          <dl>
            <Row label="Deadline" value={rules.deadline ? formatDate(rules.deadline) : null} />
            <Row label="Portal" value={rules.portal} />
            <Row label="Bid system" value={rules.bid_system?.replace('_', ' ')} />
            <Row label="EMD" value={rules.emd?.amount_inr ? inr(rules.emd.amount_inr) : null} />
            <Row label="EMD exemption" value={rules.emd?.exemption} />
            <Row
              label="Bid validity"
              value={rules.validity_days ? `${rules.validity_days} days` : null}
            />
            <Row label="Signing" value={rules.signing} />
          </dl>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Format rules</CardTitle>
          <CardDescription>Applied automatically to every generated document.</CardDescription>
        </CardHeader>
        <CardContent>
          <dl>
            <Row
              label="Page limit"
              value={format?.page_limit ? `${format.page_limit} pages (technical proposal)` : null}
            />
            <Row
              label="Font"
              value={
                format?.font
                  ? `${format.font}${format.font_size ? ` ${format.font_size} pt` : ''}`
                  : null
              }
            />
            <Row label="Margins" value={format?.margins_in ? `${format.margins_in} inch` : null} />
            <Row label="File types" value={format?.file_types.join(', ')} />
            <Row
              label="Max file size"
              value={format?.max_file_mb ? `${format.max_file_mb} MB` : null}
            />
            <Row label="File naming" value={rules.naming} />
          </dl>
        </CardContent>
      </Card>
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>What to submit</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          {(rules.covers ?? []).length === 0 ? (
            <p className="text-sm text-muted-foreground">No covers or volumes were found.</p>
          ) : null}
          {(rules.covers ?? []).map((cover) => (
            <div key={cover.name} className="rounded-md border border-border p-3">
              <h3 className="mb-2 text-sm font-semibold">{cover.name}</h3>
              <ul className="flex list-disc flex-col gap-1 pl-5 text-sm">
                {cover.documents.map((doc) => (
                  <li key={doc}>{doc}</li>
                ))}
              </ul>
            </div>
          ))}
        </CardContent>
      </Card>
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>Eligibility checklist</CardTitle>
          <CardDescription>
            Checked against your company profile and knowledge base.
          </CardDescription>
        </CardHeader>
        <CardContent className="px-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="pl-6">Criterion</TableHead>
                <TableHead>Evidence to attach</TableHead>
                <TableHead className="w-24">Status</TableHead>
                <TableHead>Note</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(rules.eligibility ?? []).map((item) => (
                <TableRow key={item.criterion}>
                  <TableCell className="pl-6 whitespace-normal">{item.criterion}</TableCell>
                  <TableCell className="whitespace-normal text-muted-foreground">
                    {item.evidence}
                  </TableCell>
                  <TableCell>
                    <EligibilityStatus item={item} />
                  </TableCell>
                  <TableCell className="text-xs whitespace-normal text-muted-foreground">
                    {item.reason}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>Forms and annexures</CardTitle>
          <CardDescription>
            Filled from your company profile in the generated package.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2">
          {(rules.forms ?? []).map((form) => (
            <div
              key={form.code}
              className="flex flex-col gap-2 rounded-md border border-border p-3"
            >
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-sm font-semibold">
                  {form.code}: {form.title}
                </h3>
                {form.unfilled.length ? (
                  <Badge variant="outline" className="border-status-partial/60 text-status-partial">
                    {form.unfilled.length} to fill
                  </Badge>
                ) : (
                  <Badge variant="outline" className="border-status-full/50 text-status-full">
                    Ready
                  </Badge>
                )}
              </div>
              <p className="text-xs text-muted-foreground">
                {form.fields.length ? `${form.fields.length} fields` : 'No fill-in fields'}
                {form.page ? ` · page ${form.page}` : ''}
              </p>
              {form.unfilled.length ? (
                <p className="text-xs">
                  Missing in profile: {form.unfilled.map((f) => f.replaceAll('_', ' ')).join(', ')}
                </p>
              ) : null}
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
