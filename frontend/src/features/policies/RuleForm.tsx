import { Braces, Plus, Trash2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { toast } from 'sonner'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { usePolicyFields, useSaveRule } from '@/features/policies/api'
import {
  OPS,
  isLeaf,
  type Condition,
  type FieldDef,
  type LeafCondition,
  type RuleSpec,
  type Scope,
  type Severity,
} from '@/features/policies/types'
import { errorMessage } from '@/lib/api'

type Row = { field: string; op: string; value: string }
type Builder = { combinator: 'all' | 'any'; rows: Row[] } | null

const EMPTY_ROW: Row = { field: '', op: 'eq', value: '' }

function valueText(value: unknown): string {
  if (Array.isArray(value)) return value.map((v) => valueText(v)).join(', ')
  if (value === undefined || value === null) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return `${value}`
  return JSON.stringify(value)
}

function toRow(leaf: LeafCondition): Row {
  return { field: leaf.field, op: leaf.op, value: valueText(leaf.value) }
}

/** Builder state for a condition, or null when it is too nested for the form (use JSON instead). */
function toBuilder(condition: Condition | null): Builder {
  if (!condition) return { combinator: 'all', rows: [] }
  if (isLeaf(condition)) return { combinator: 'all', rows: [toRow(condition)] }
  if ('all' in condition && condition.all.every(isLeaf))
    return { combinator: 'all', rows: condition.all.map(toRow) }
  if ('any' in condition && condition.any.every(isLeaf))
    return { combinator: 'any', rows: condition.any.map(toRow) }
  return null
}

function parseValue(row: Row, fields: FieldDef[]): unknown {
  const op = OPS.find((o) => o.value === row.op)
  if (!op?.needsValue) return undefined
  if (op.list)
    return row.value
      .split(',')
      .map((v) => v.trim())
      .filter(Boolean)
  const field = fields.find((f) => f.name === row.field)
  if (field?.type === 'number' && row.value.trim() !== '' && !Number.isNaN(Number(row.value)))
    return Number(row.value)
  return row.value
}

function fromBuilder(builder: Builder, fields: FieldDef[]): Condition | null {
  if (!builder || builder.rows.length === 0) return null
  const leaves = builder.rows.map((row) => {
    const value = parseValue(row, fields)
    return value === undefined
      ? { field: row.field, op: row.op }
      : { field: row.field, op: row.op, value }
  })
  if (leaves.length === 1 && leaves[0]) return leaves[0]
  return builder.combinator === 'all' ? { all: leaves } : { any: leaves }
}

function ConditionRows({
  label,
  hint,
  builder,
  setBuilder,
  fields,
  allowEmpty,
}: {
  label: string
  hint: string
  builder: NonNullable<Builder>
  setBuilder: (b: NonNullable<Builder>) => void
  fields: FieldDef[]
  allowEmpty: boolean
}) {
  const update = (index: number, patch: Partial<Row>) =>
    setBuilder({
      ...builder,
      rows: builder.rows.map((r, i) => (i === index ? { ...r, ...patch } : r)),
    })
  return (
    <fieldset className="flex flex-col gap-2 rounded-lg border border-border p-3">
      <legend className="px-1 text-sm font-medium">{label}</legend>
      <p className="text-xs text-muted-foreground">{hint}</p>
      {builder.rows.length > 1 ? (
        <Select
          value={builder.combinator}
          onValueChange={(v) => setBuilder({ ...builder, combinator: v as 'all' | 'any' })}
        >
          <SelectTrigger size="sm" className="w-56" aria-label={`${label}: how conditions combine`}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All conditions are true</SelectItem>
            <SelectItem value="any">Any condition is true</SelectItem>
          </SelectContent>
        </Select>
      ) : null}
      {builder.rows.map((row, index) => {
        const op = OPS.find((o) => o.value === row.op)
        const field = fields.find((f) => f.name === row.field)
        return (
          <div key={index} className="grid gap-2 sm:grid-cols-[1.4fr_1fr_1.2fr_auto]">
            <Select
              value={row.field || undefined}
              onValueChange={(v) => update(index, { field: v })}
            >
              <SelectTrigger size="sm" aria-label="Field">
                <SelectValue placeholder="Choose a field" />
              </SelectTrigger>
              <SelectContent>
                {fields.map((f) => (
                  <SelectItem key={f.name} value={f.name}>
                    {f.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={row.op} onValueChange={(v) => update(index, { op: v })}>
              <SelectTrigger size="sm" aria-label="Operator">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {OPS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {op?.needsValue ? (
              <Input
                aria-label="Value"
                className="h-7"
                placeholder={
                  op.list
                    ? 'comma, separated, values'
                    : field?.type === 'number'
                      ? 'number'
                      : 'value'
                }
                value={row.value}
                onChange={(event) => update(index, { value: event.target.value })}
              />
            ) : (
              <span className="self-center text-xs text-muted-foreground">no value needed</span>
            )}
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label="Remove condition"
              disabled={!allowEmpty && builder.rows.length === 1}
              onClick={() =>
                setBuilder({ ...builder, rows: builder.rows.filter((_, i) => i !== index) })
              }
            >
              <Trash2 />
            </Button>
            {field ? (
              <p className="text-xs text-muted-foreground sm:col-span-4">{field.description}</p>
            ) : null}
          </div>
        )
      })}
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="self-start"
        onClick={() => setBuilder({ ...builder, rows: [...builder.rows, { ...EMPTY_ROW }] })}
      >
        <Plus aria-hidden="true" /> Add condition
      </Button>
    </fieldset>
  )
}

type RuleFormProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  initial: RuleSpec | null
  dbId: number | null
}

const BLANK: RuleSpec = {
  id: '',
  name: '',
  description: '',
  scope: 'requirement',
  when: null,
  flag_if: { field: '', op: 'eq', value: '' },
  severity: 'medium',
  message: '',
  enabled: true,
}

export function RuleForm({ open, onOpenChange, initial, dbId }: RuleFormProps) {
  const start = initial ?? BLANK
  const fieldsQuery = usePolicyFields()
  const save = useSaveRule()
  const [meta, setMeta] = useState({
    id: start.id,
    name: start.name,
    description: start.description,
    scope: start.scope,
    severity: start.severity,
    message: start.message,
    enabled: start.enabled,
  })
  const initialWhen = toBuilder(start.when)
  const initialFlag = toBuilder(start.flag_if)
  const [jsonMode, setJsonMode] = useState(initialWhen === null || initialFlag === null)
  const [when, setWhen] = useState<NonNullable<Builder>>(
    initialWhen ?? { combinator: 'all', rows: [] },
  )
  const [flag, setFlag] = useState<NonNullable<Builder>>(
    initialFlag && initialFlag.rows.length
      ? initialFlag
      : { combinator: 'all', rows: [{ ...EMPTY_ROW }] },
  )
  const [json, setJson] = useState(() => JSON.stringify(start, null, 2))
  const [error, setError] = useState<string | null>(null)

  const fields = useMemo(
    () => (fieldsQuery.data ?? []).filter((f) => f.scopes.includes(meta.scope)),
    [fieldsQuery.data, meta.scope],
  )

  const build = (): RuleSpec | null => {
    if (jsonMode) {
      try {
        return JSON.parse(json) as RuleSpec
      } catch {
        setError('The JSON is not valid.')
        return null
      }
    }
    const flagIf = fromBuilder(flag, fields)
    if (!flagIf) {
      setError('Add at least one "flag if" condition.')
      return null
    }
    return { ...meta, id: meta.id || meta.name, when: fromBuilder(when, fields), flag_if: flagIf }
  }

  const submit = () => {
    setError(null)
    const rule = build()
    if (!rule) return
    save.mutate(
      { dbId, rule },
      {
        onSuccess: () => {
          toast.success(`Rule "${rule.name}" saved. Re-run the audit to apply it.`)
          onOpenChange(false)
        },
        onError: (e) => setError(errorMessage(e)),
      },
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92svh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>{dbId ? 'Edit rule' : 'New policy rule'}</DialogTitle>
          <DialogDescription>
            No code needed: the rule is saved as data and applies on the next "Re-run audit".
          </DialogDescription>
        </DialogHeader>
        <div className="flex items-center justify-end gap-2">
          <Label htmlFor="json-mode" className="text-xs text-muted-foreground">
            <Braces aria-hidden="true" className="inline size-3.5" /> Edit as JSON
          </Label>
          <Switch
            id="json-mode"
            checked={jsonMode}
            onCheckedChange={(on) => {
              if (on) {
                const rule = build()
                if (rule) setJson(JSON.stringify(rule, null, 2))
              }
              setJsonMode(on)
            }}
          />
        </div>
        {jsonMode ? (
          <Textarea
            aria-label="Rule JSON"
            className="min-h-80 font-mono text-xs"
            value={json}
            onChange={(event) => setJson(event.target.value)}
          />
        ) : (
          <div className="flex flex-col gap-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="rule-name">Rule name</Label>
                <Input
                  id="rule-name"
                  placeholder="e.g. Penalty above 1%"
                  value={meta.name}
                  onChange={(e) => setMeta({ ...meta, name: e.target.value })}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="rule-id">Rule ID</Label>
                <Input
                  id="rule-id"
                  placeholder="generated from the name"
                  value={meta.id}
                  onChange={(e) => setMeta({ ...meta, id: e.target.value })}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="rule-scope">Checks</Label>
                <Select
                  value={meta.scope}
                  onValueChange={(v) => {
                    setMeta({ ...meta, scope: v as Scope })
                    setWhen({ combinator: 'all', rows: [] })
                    setFlag({ combinator: 'all', rows: [{ ...EMPTY_ROW }] })
                  }}
                >
                  <SelectTrigger id="rule-scope">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="requirement">Each requirement and its answer</SelectItem>
                    <SelectItem value="tender">The tender as a whole</SelectItem>
                    <SelectItem value="company">The company profile</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="rule-severity">Severity</Label>
                <Select
                  value={meta.severity}
                  onValueChange={(v) => setMeta({ ...meta, severity: v as Severity })}
                >
                  <SelectTrigger id="rule-severity">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="high">High — blocks the package</SelectItem>
                    <SelectItem value="medium">Medium</SelectItem>
                    <SelectItem value="low">Low</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            {meta.scope === 'requirement' ? (
              <ConditionRows
                label="Applies when (optional)"
                hint="Limit the rule to some requirements, e.g. requirement.text matches pattern penalty."
                builder={when}
                setBuilder={setWhen}
                fields={fields}
                allowEmpty
              />
            ) : null}
            <ConditionRows
              label="Flag if"
              hint="An exception is raised when these conditions are true."
              builder={flag}
              setBuilder={setFlag}
              fields={fields}
              allowEmpty={false}
            />
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="rule-message">Message</Label>
              <Input
                id="rule-message"
                placeholder="{requirement.code}: penalty of {requirement.max_percent}% exceeds our cap"
                value={meta.message}
                onChange={(e) => setMeta({ ...meta, message: e.target.value })}
              />
              <p className="text-xs text-muted-foreground">
                Use {'{field.name}'} to insert values from the checked item.
              </p>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="rule-description">Why this rule exists (optional)</Label>
              <Input
                id="rule-description"
                value={meta.description}
                onChange={(e) => setMeta({ ...meta, description: e.target.value })}
              />
            </div>
          </div>
        )}
        {error ? (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button disabled={save.isPending} onClick={submit}>
            {save.isPending ? 'Saving…' : 'Save rule'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
