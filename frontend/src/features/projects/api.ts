import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/lib/api'
import { queryKeys, type RequirementFilters } from '@/lib/queryKeys'
import type {
  AuditEntry,
  Conflict,
  Criterion,
  DiffPart,
  GoNoGo,
  JobStarted,
  OutlineSection,
  PackageInfo,
  ProjectSummary,
  RequirementList,
  RequirementRow,
  SubmissionRules,
  Validation,
} from '@/features/projects/types'

export function useProjects() {
  return useQuery({
    queryKey: queryKeys.projects,
    queryFn: () => api<ProjectSummary[]>('/projects'),
  })
}

export function useProject(id: number) {
  return useQuery({
    queryKey: queryKeys.project(id),
    queryFn: () => api<ProjectSummary>(`/projects/${id}`),
  })
}

export function useRequirements(id: number, filters: RequirementFilters) {
  return useQuery({
    queryKey: queryKeys.requirements(id, filters),
    queryFn: () => api<RequirementList>(`/projects/${id}/requirements`, { query: filters }),
    placeholderData: (previous) => previous,
  })
}

export function useRules(id: number) {
  return useQuery({
    queryKey: queryKeys.rules(id),
    queryFn: () => api<SubmissionRules>(`/projects/${id}/rules`),
  })
}

export function useCriteria(id: number) {
  return useQuery({
    queryKey: queryKeys.criteria(id),
    queryFn: () => api<Criterion[]>(`/projects/${id}/criteria`),
  })
}

export function useWinThemes(id: number) {
  return useQuery({
    queryKey: queryKeys.winThemes(id),
    queryFn: () => api<string[]>(`/projects/${id}/win-themes`),
  })
}

export function useGoNoGo(id: number) {
  return useQuery({
    queryKey: queryKeys.goNoGo(id),
    queryFn: () => api<GoNoGo>(`/projects/${id}/go-no-go`),
    staleTime: 0,
  })
}

export function useValidation(id: number) {
  return useQuery({
    queryKey: queryKeys.validate(id),
    queryFn: () => api<Validation>(`/projects/${id}/validate`),
    staleTime: 0,
  })
}

export function useOutline(id: number) {
  return useQuery({
    queryKey: queryKeys.outline(id),
    queryFn: () => api<OutlineSection[]>(`/projects/${id}/outline`),
  })
}

export function useConflicts(id: number) {
  return useQuery({
    queryKey: queryKeys.conflicts(id),
    queryFn: () => api<Conflict[]>(`/projects/${id}/conflicts`),
  })
}

export function usePackageInfo(id: number) {
  return useQuery({
    queryKey: queryKeys.packageInfo(id),
    queryFn: () => api<PackageInfo>(`/projects/${id}/package`),
  })
}

export function useHistory(responseId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.history(responseId ?? 0),
    queryFn: () => api<AuditEntry[]>(`/responses/${responseId}/history`),
    enabled: Boolean(responseId),
  })
}

export function useDiff(requirementId: number, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.diff(requirementId),
    queryFn: () => api<DiffPart[]>(`/requirements/${requirementId}/diff`),
    enabled,
  })
}

/** Invalidate everything derived from a project's rows (after drafting, editing, addenda). */
export function useInvalidateProject() {
  const client = useQueryClient()
  return (id: number) => {
    for (const key of [
      queryKeys.project(id),
      queryKeys.requirementsAll(id),
      queryKeys.criteria(id),
      queryKeys.rules(id),
      queryKeys.goNoGo(id),
      queryKeys.validate(id),
      queryKeys.outline(id),
      queryKeys.conflicts(id),
      queryKeys.packageInfo(id),
      queryKeys.projects,
    ]) {
      void client.invalidateQueries({ queryKey: key })
    }
  }
}

export function useStartJob(path: (id: number) => string) {
  return useMutation({ mutationFn: (id: number) => api<JobStarted>(path(id), { method: 'POST' }) })
}

export function useSaveWinThemes(id: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (themes: string[]) =>
      api<string[]>(`/projects/${id}/win-themes`, { method: 'PUT', body: { themes } }),
    onSuccess: (themes) => client.setQueryData(queryKeys.winThemes(id), themes),
  })
}

export function useSetCompetition(id: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (rating: number) =>
      api<GoNoGo>(`/projects/${id}/go-no-go`, {
        method: 'PUT',
        body: { competition_rating: rating },
      }),
    onSuccess: (result) => {
      client.setQueryData(queryKeys.goNoGo(id), result)
      void client.invalidateQueries({ queryKey: queryKeys.project(id) })
    },
  })
}

export function useSetOutcome(id: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (outcome: 'unknown' | 'won' | 'lost') =>
      api<ProjectSummary>(`/projects/${id}/outcome`, { method: 'PUT', body: { outcome } }),
    onSuccess: (project) => client.setQueryData(queryKeys.project(id), project),
  })
}

export type ResponsePatch = {
  answer?: string | null
  status?: string
  approved?: boolean
  override_reason?: string
}

export function usePatchResponse(projectId: number) {
  const invalidate = useInvalidateProject()
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ responseId, patch }: { responseId: number; patch: ResponsePatch }) =>
      api<RequirementRow>(`/responses/${responseId}`, { method: 'PATCH', body: patch }),
    onSuccess: (row) => {
      if (row.response)
        void client.invalidateQueries({ queryKey: queryKeys.history(row.response.id) })
      invalidate(projectId)
    },
  })
}

export function useRedraft() {
  return useMutation({
    mutationFn: ({ responseId, hint }: { responseId: number; hint?: string }) =>
      api<JobStarted>(`/responses/${responseId}/redraft`, {
        method: 'POST',
        body: { hint: hint || null },
      }),
  })
}

export function useRunConsistency(id: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => api<Conflict[]>(`/projects/${id}/consistency`, { method: 'POST' }),
    onSuccess: (conflicts) => {
      client.setQueryData(queryKeys.conflicts(id), conflicts)
      void client.invalidateQueries({ queryKey: queryKeys.validate(id) })
    },
  })
}

export function useResolveConflict(id: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (conflictId: number) =>
      api<Conflict>(`/projects/${id}/conflicts/${conflictId}/resolve`, { method: 'PUT' }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.conflicts(id) })
      void client.invalidateQueries({ queryKey: queryKeys.validate(id) })
    },
  })
}

export function useGenerateOutline(id: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => api<OutlineSection[]>(`/projects/${id}/outline`, { method: 'POST' }),
    onSuccess: (sections) => client.setQueryData(queryKeys.outline(id), sections),
  })
}

export function useUploadAddendum(id: number) {
  return useMutation({
    mutationFn: (file: File) => {
      const form = new FormData()
      form.append('file', file)
      return api<JobStarted>(`/projects/${id}/addenda`, { method: 'POST', form })
    },
  })
}

export function useCreateProject() {
  return useMutation({
    mutationFn: ({
      main,
      attachments,
      title,
    }: {
      main: File
      attachments: File[]
      title: string
    }) => {
      const form = new FormData()
      form.append('main', main)
      for (const file of attachments) form.append('attachments', file)
      form.append('title', title)
      return api<JobStarted>('/projects', { method: 'POST', form })
    },
  })
}

export function useDeleteProject() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api<void>(`/projects/${id}`, { method: 'DELETE' }),
    onSuccess: () => void client.invalidateQueries({ queryKey: queryKeys.projects }),
  })
}
