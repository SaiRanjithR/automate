import type { JobStep } from '@/features/jobs/JobProgress'

export const ANALYSE_STEPS: JobStep[] = [
  { stage: 'parsing', label: 'Parsing the documents' },
  { stage: 'requirements', label: 'Finding requirements' },
  { stage: 'rules', label: 'Reading submission rules' },
  { stage: 'criteria', label: 'Reading scoring criteria' },
]
