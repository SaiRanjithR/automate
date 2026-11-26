export type Scope = 'requirement' | 'tender' | 'company'
export type Severity = 'high' | 'medium' | 'low'

export type LeafCondition = { field: string; op: string; value?: unknown }
export type Condition =
  LeafCondition | { all: Condition[] } | { any: Condition[] } | { not: Condition }

export type RuleSpec = {
  id: string
  name: string
  description: string
  scope: Scope
  when: Condition | null
  flag_if: Condition
  severity: Severity
  message: string
  enabled: boolean
}

export type PolicyRule = RuleSpec & { db_id: number | null; source: string; editable: boolean }
export type PolicyFile = { name: string; modified: string; rules: number; error: string | null }
export type Policies = {
  rules: PolicyRule[]
  files: PolicyFile[]
  errors: string[]
  policy_dir: string
}
export type FieldDef = {
  name: string
  type: 'text' | 'number' | 'boolean' | 'list'
  scopes: Scope[]
  description: string
}

export type Finding = {
  key: string
  rule_id: string
  rule_name: string
  source: string
  scope: Scope
  severity: Severity
  message: string
  target: { requirement_id: number; req_code: string } | null
  new: boolean
}

export type AuditRun = {
  id: number
  created_at: string
  findings: Finding[]
  errors: string[]
  rules_evaluated: number
  resolved: number
  new_count: number
  counts: Record<Severity, number>
}

export const OPS: { value: string; label: string; needsValue: boolean; list?: boolean }[] = [
  { value: 'eq', label: 'equals', needsValue: true },
  { value: 'neq', label: 'does not equal', needsValue: true },
  { value: 'gt', label: 'is greater than', needsValue: true },
  { value: 'gte', label: 'is at least', needsValue: true },
  { value: 'lt', label: 'is less than', needsValue: true },
  { value: 'lte', label: 'is at most', needsValue: true },
  { value: 'contains', label: 'contains', needsValue: true },
  { value: 'not_contains', label: 'does not contain', needsValue: true },
  { value: 'contains_any', label: 'contains any of', needsValue: true, list: true },
  { value: 'not_contains_any', label: 'contains none of', needsValue: true, list: true },
  { value: 'matches', label: 'matches pattern', needsValue: true },
  { value: 'not_matches', label: 'does not match pattern', needsValue: true },
  { value: 'in', label: 'is one of', needsValue: true, list: true },
  { value: 'not_in', label: 'is not one of', needsValue: true, list: true },
  { value: 'exists', label: 'has a value', needsValue: false },
  { value: 'not_exists', label: 'is empty', needsValue: false },
  { value: 'is_true', label: 'is true', needsValue: false },
  { value: 'is_false', label: 'is false', needsValue: false },
]

export function isLeaf(condition: Condition): condition is LeafCondition {
  return 'field' in condition
}

/** Plain-English summary of a condition, e.g. "requirement.max_percent is greater than 1". */
export function describe(condition: Condition | null): string {
  if (!condition) return ''
  if (isLeaf(condition)) {
    const op = OPS.find((o) => o.value === condition.op)
    const value = Array.isArray(condition.value) ? condition.value.join(', ') : condition.value
    return `${condition.field} ${op?.label ?? condition.op}${op?.needsValue ? ` ${String(value)}` : ''}`
  }
  if ('all' in condition) return condition.all.map(describe).join(' AND ')
  if ('any' in condition) return condition.any.map(describe).join(' OR ')
  return `NOT (${describe(condition.not)})`
}
