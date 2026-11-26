import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { AuditRun, FieldDef, Policies, PolicyRule, RuleSpec } from '@/features/policies/types'
import { api } from '@/lib/api'

export const policyKeys = {
  all: ['policies'] as const,
  fields: ['policies', 'fields'] as const,
  audit: (projectId: number) => ['audit', projectId] as const,
}

export function usePolicies() {
  return useQuery({
    queryKey: policyKeys.all,
    queryFn: () => api<Policies>('/policies'),
    staleTime: 0,
  })
}

export function usePolicyFields() {
  return useQuery({
    queryKey: policyKeys.fields,
    queryFn: () => api<FieldDef[]>('/policies/fields'),
    staleTime: Infinity,
  })
}

export function useSaveRule() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ dbId, rule }: { dbId: number | null; rule: RuleSpec }) =>
      dbId
        ? api<PolicyRule>(`/policies/${dbId}`, { method: 'PUT', body: rule })
        : api<PolicyRule>('/policies', { method: 'POST', body: rule }),
    onSuccess: () => void client.invalidateQueries({ queryKey: policyKeys.all }),
  })
}

export function useToggleRule() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ dbId, enabled }: { dbId: number; enabled: boolean }) =>
      api<PolicyRule>(`/policies/${dbId}`, { method: 'PATCH', body: { enabled } }),
    onSuccess: () => void client.invalidateQueries({ queryKey: policyKeys.all }),
  })
}

export function useDeleteRule() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (dbId: number) => api<void>(`/policies/${dbId}`, { method: 'DELETE' }),
    onSuccess: () => void client.invalidateQueries({ queryKey: policyKeys.all }),
  })
}

export function useImportRules() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (rules: unknown[]) =>
      api<{ created: number; updated: number; errors: string[] }>('/policies/import', {
        method: 'POST',
        body: { rules },
      }),
    onSuccess: () => void client.invalidateQueries({ queryKey: policyKeys.all }),
  })
}

export function useAudit(projectId: number) {
  return useQuery({
    queryKey: policyKeys.audit(projectId),
    queryFn: () => api<AuditRun | null>(`/projects/${projectId}/audit`),
    staleTime: 0,
  })
}

export function useRerunAudit(projectId: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => api<AuditRun>(`/projects/${projectId}/audit`, { method: 'POST' }),
    onSuccess: (run) => {
      client.setQueryData(policyKeys.audit(projectId), run)
      void client.invalidateQueries({ queryKey: ['validate', projectId] })
      void client.invalidateQueries({ queryKey: ['project', projectId] })
    },
  })
}
