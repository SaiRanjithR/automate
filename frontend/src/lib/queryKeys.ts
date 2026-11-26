export type RequirementFilters = {
  status?: string
  category?: string
  mandatory?: boolean
  criterion_id?: number
  has_issues?: boolean
  version_status?: string
  q?: string
}

export const queryKeys = {
  me: ['me'] as const,
  company: ['company'] as const,
  knowledge: ['knowledge'] as const,
  knowledgeSearch: (q: string) => ['knowledge', 'search', q] as const,
  projects: ['projects'] as const,
  project: (id: number) => ['project', id] as const,
  requirements: (id: number, filters: RequirementFilters = {}) =>
    ['requirements', id, filters] as const,
  requirementsAll: (id: number) => ['requirements', id] as const,
  rules: (id: number) => ['rules', id] as const,
  criteria: (id: number) => ['criteria', id] as const,
  winThemes: (id: number) => ['win-themes', id] as const,
  goNoGo: (id: number) => ['go-no-go', id] as const,
  validate: (id: number) => ['validate', id] as const,
  outline: (id: number) => ['outline', id] as const,
  conflicts: (id: number) => ['conflicts', id] as const,
  packageInfo: (id: number) => ['package', id] as const,
  history: (responseId: number) => ['history', responseId] as const,
  diff: (requirementId: number) => ['diff', requirementId] as const,
  job: (id: number) => ['job', id] as const,
}
