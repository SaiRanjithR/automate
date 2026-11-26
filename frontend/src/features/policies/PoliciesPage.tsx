import { Copy, Download, FileCode2, Pencil, Plus, Trash2, Upload } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingRows } from '@/components/common/LoadingRows'
import { PageHeader } from '@/components/common/PageHeader'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Switch } from '@/components/ui/switch'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { useDeleteRule, useImportRules, usePolicies, useToggleRule } from '@/features/policies/api'
import { RuleForm } from '@/features/policies/RuleForm'
import { SeverityBadge } from '@/features/policies/SeverityBadge'
import { describe, type PolicyRule, type RuleSpec } from '@/features/policies/types'
import { api, errorMessage } from '@/lib/api'

const SCOPE_LABEL = {
  requirement: 'Each requirement',
  tender: 'Tender',
  company: 'Company',
} as const

function stripMeta(rule: PolicyRule): RuleSpec {
  return {
    id: rule.id,
    name: rule.name,
    description: rule.description,
    scope: rule.scope,
    when: rule.when,
    flag_if: rule.flag_if,
    severity: rule.severity,
    message: rule.message,
    enabled: rule.enabled,
  }
}

export function PoliciesPage() {
  const { data, isPending, error, refetch } = usePolicies()
  const toggle = useToggleRule()
  const remove = useDeleteRule()
  const importRules = useImportRules()
  const [form, setForm] = useState<{
    rule: RuleSpec | null
    dbId: number | null
    key: number
  } | null>(null)
  const [importOpen, setImportOpen] = useState(false)
  const [importText, setImportText] = useState('')

  const openForm = (rule: RuleSpec | null, dbId: number | null) =>
    setForm({ rule, dbId, key: Date.now() })

  const exportRules = async () => {
    const payload = await api<{ rules: unknown[] }>('/policies/export')
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = 'bidready-policies.json'
    link.click()
    URL.revokeObjectURL(link.href)
  }

  const runImport = () => {
    let rules: unknown[]
    try {
      const parsed: unknown = JSON.parse(importText)
      rules = Array.isArray(parsed) ? parsed : ((parsed as { rules?: unknown[] }).rules ?? [])
    } catch {
      toast.error('That is not valid JSON')
      return
    }
    importRules.mutate(rules, {
      onSuccess: (result) => {
        toast.success(`Imported: ${result.created} new, ${result.updated} updated`)
        if (result.errors.length) toast.warning(result.errors.slice(0, 3).join('\n'))
        setImportOpen(false)
        setImportText('')
      },
      onError: (e) => toast.error(errorMessage(e)),
    })
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Policies"
        description="Business, financial and compliance rules checked by every audit. Add or change them here or in a JSON / YAML file — no code, no restart."
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => setImportOpen(true)}>
              <Upload aria-hidden="true" /> Import JSON
            </Button>
            <Button variant="outline" onClick={() => void exportRules()}>
              <Download aria-hidden="true" /> Export
            </Button>
            <Button onClick={() => openForm(null, null)}>
              <Plus aria-hidden="true" /> New rule
            </Button>
          </div>
        }
      />
      {isPending ? (
        <LoadingRows rows={6} />
      ) : error ? (
        <ErrorState message={errorMessage(error)} onRetry={() => void refetch()} />
      ) : (
        <>
          {data.errors.length ? (
            <Alert variant="destructive">
              <AlertTitle>Some rules were skipped</AlertTitle>
              <AlertDescription>
                <ul className="list-disc pl-4">
                  {data.errors.map((e) => (
                    <li key={e}>{e}</li>
                  ))}
                </ul>
              </AlertDescription>
            </Alert>
          ) : null}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileCode2 aria-hidden="true" className="size-4" /> Policy files
              </CardTitle>
              <CardDescription>
                Files in <code className="font-mono text-xs">{data.policy_dir}</code> are read again
                on every audit. Edit one, then click Re-run audit on a project.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {data.files.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No policy files yet. Add a .yaml or .json file to that folder.
                </p>
              ) : (
                data.files.map((file) => (
                  <span
                    key={file.name}
                    className="rounded-md border border-border px-3 py-1.5 text-sm"
                  >
                    <span className="font-medium">{file.name}</span>{' '}
                    <span className="text-muted-foreground">
                      · {file.rules} rules · changed{' '}
                      {new Date(file.modified).toLocaleString('en-IN')}
                    </span>
                    {file.error ? (
                      <span className="block text-xs text-destructive">{file.error}</span>
                    ) : null}
                  </span>
                ))
              )}
            </CardContent>
          </Card>
          {data.rules.length === 0 ? (
            <EmptyState
              title="No rules yet"
              description="Create a rule or drop a policy file in the policy folder."
            />
          ) : (
            <Card>
              <CardContent className="px-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="pl-6">Rule</TableHead>
                      <TableHead>Checks</TableHead>
                      <TableHead>Flags when</TableHead>
                      <TableHead>Severity</TableHead>
                      <TableHead>Source</TableHead>
                      <TableHead>On</TableHead>
                      <TableHead className="w-24" />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.rules.map((rule) => (
                      <TableRow
                        key={`${rule.source}-${rule.id}`}
                        className={rule.enabled ? '' : 'opacity-60'}
                      >
                        <TableCell className="pl-6 whitespace-normal">
                          <p className="font-medium">{rule.name}</p>
                          <p className="font-mono text-xs text-muted-foreground">{rule.id}</p>
                        </TableCell>
                        <TableCell className="text-sm">{SCOPE_LABEL[rule.scope]}</TableCell>
                        <TableCell className="max-w-md font-mono text-xs whitespace-normal text-muted-foreground">
                          {rule.when ? (
                            <span className="block">when {describe(rule.when)}</span>
                          ) : null}
                          <span className="block text-foreground">{describe(rule.flag_if)}</span>
                        </TableCell>
                        <TableCell>
                          <SeverityBadge severity={rule.severity} />
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="font-mono text-xs">
                            {rule.source === 'ui' ? 'app' : rule.source.replace('file:', '')}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Switch
                            aria-label={`Enable ${rule.name}`}
                            checked={rule.enabled}
                            disabled={!rule.editable}
                            onCheckedChange={(enabled) =>
                              rule.db_id && toggle.mutate({ dbId: rule.db_id, enabled })
                            }
                          />
                        </TableCell>
                        <TableCell>
                          {rule.editable && rule.db_id ? (
                            <div className="flex">
                              <Button
                                variant="ghost"
                                size="icon-sm"
                                aria-label={`Edit ${rule.name}`}
                                onClick={() => openForm(stripMeta(rule), rule.db_id)}
                              >
                                <Pencil />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon-sm"
                                aria-label={`Delete ${rule.name}`}
                                onClick={() =>
                                  rule.db_id &&
                                  remove.mutate(rule.db_id, {
                                    onSuccess: () => toast.success('Rule deleted'),
                                  })
                                }
                              >
                                <Trash2 />
                              </Button>
                            </div>
                          ) : (
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              aria-label={`Copy ${rule.name} into the app to edit it`}
                              title="Copy into the app to edit"
                              onClick={() =>
                                openForm({ ...stripMeta(rule), id: `${rule.id}-copy` }, null)
                              }
                            >
                              <Copy />
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </>
      )}
      {form ? (
        <RuleForm
          key={form.key}
          open
          onOpenChange={(open) => !open && setForm(null)}
          initial={form.rule}
          dbId={form.dbId}
        />
      ) : null}
      <Dialog open={importOpen} onOpenChange={setImportOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Import rules from JSON</DialogTitle>
            <DialogDescription>
              Paste {'{"rules": [...]}'} or a list of rules. Rules with an existing ID are updated.
            </DialogDescription>
          </DialogHeader>
          <Textarea
            aria-label="Rules JSON"
            className="min-h-72 font-mono text-xs"
            placeholder='{"rules": [{"id": "emd-limit", "name": "EMD above 5 lakh", "scope": "tender", "flag_if": {"field": "tender.emd_inr", "op": "gt", "value": 500000}, "severity": "medium"}]}'
            value={importText}
            onChange={(event) => setImportText(event.target.value)}
          />
          <DialogFooter>
            <Button variant="ghost" onClick={() => setImportOpen(false)}>
              Cancel
            </Button>
            <Button disabled={!importText.trim() || importRules.isPending} onClick={runImport}>
              Import
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
