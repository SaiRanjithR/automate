import type { Schemas } from '@/lib/api'

export type ProjectSummary = Schemas['ProjectSummary']
export type RequirementRow = Schemas['RequirementOut']
export type ResponseData = Schemas['ResponseOut']
export type RequirementList = Schemas['RequirementList']
export type Criterion = Schemas['CriterionOut']
export type OutlineSection = Schemas['OutlineSectionOut']
export type Conflict = Schemas['ConflictOut']
export type Job = Schemas['JobOut']
export type JobStarted = Schemas['JobStarted']

export type Citation = {
  chunk_id: number
  doc_id: number
  filename: string
  page: number
  quote: string
  /** won | lost | unknown — outcome of the bid the evidence came from */
  outcome?: string
  /** rfp_clause = a commitment that cites the tender clause, not company evidence */
  kind?: 'rfp_clause'
}

export type EligibilityItem = {
  criterion: string
  evidence: string
  page: number | null
  status: 'met' | 'missing' | 'manual'
  reason: string
}

export type FormSpec = {
  code: string
  title: string
  page: number | null
  fields: string[]
  text: string
  unfilled: string[]
}

export type SubmissionRules = {
  title?: string | null
  tender_no?: string | null
  buyer?: string | null
  deadline?: string | null
  portal?: string | null
  bid_system?: string | null
  covers?: { name: string; documents: string[] }[]
  format?: {
    file_types: string[]
    max_file_mb: number | null
    page_limit: number | null
    font: string | null
    font_size: number | null
    margins_in: number | null
  }
  naming?: string | null
  signing?: string | null
  emd?: { amount_inr: number | null; exemption: string | null } | null
  validity_days?: number | null
  qcbs_split?: string | null
  min_qualifying_marks?: number | null
  eligibility?: EligibilityItem[]
  forms?: FormSpec[]
}

export type GoNoGo = {
  decision: 'go' | 'review' | 'no_go'
  score: number
  factors: { fit: number; risk: number; resources: number; competition: number }
  reasons: string[]
  eligibility_failed: string[]
  drafted: boolean
}

export type Blocker = {
  code: string
  severity: 'high' | 'medium' | 'low'
  message: string
  requirement_ids?: number[]
}

export type Validation = {
  readiness_score: number
  blockers: Blocker[]
  estimated_pages: number
  page_limit: number | null
  eligibility: EligibilityItem[]
  counts: {
    requirements: number
    mandatory: number
    approved: number
    gaps: number
    drafted: number
  }
}

export type PackageFile = {
  name: string
  label: string
  format: 'pdf' | 'docx' | 'xlsx'
  pages: number | null
}
export type PackageInfo = {
  files: PackageFile[]
  zip_name: string | null
  generated_at: string | null
}
export type DiffPart = { op: 'equal' | 'insert' | 'delete'; text: string }
export type AuditEntry = Schemas['AuditOut']
