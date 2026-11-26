export const PROJECT_TABS = [
  { value: 'overview', label: 'Overview & go / no-go' },
  { value: 'matrix', label: 'Compliance matrix' },
  { value: 'rules', label: 'Submission rules' },
  { value: 'addenda', label: 'Addenda' },
  { value: 'audit', label: 'Policy audit' },
  { value: 'package', label: 'Outline & package' },
] as const

export type ProjectTab = (typeof PROJECT_TABS)[number]['value']

export function isProjectTab(value: string | undefined): value is ProjectTab {
  return PROJECT_TABS.some((tab) => tab.value === value)
}
