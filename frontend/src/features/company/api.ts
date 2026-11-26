import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, type Schemas } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'

export type Company = Schemas['CompanyOut']
export type CompanyInput = Schemas['CompanyIn']
export type KnowledgeDoc = Schemas['KnowledgeDocOut']
export type SearchHit = Schemas['SearchHit']

export function useCompany() {
  return useQuery({ queryKey: queryKeys.company, queryFn: () => api<Company>('/company') })
}

export function useSaveCompany() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: CompanyInput) => api<Company>('/company', { method: 'PUT', body }),
    onSuccess: (company) => client.setQueryData(queryKeys.company, company),
  })
}

export function useKnowledge(poll: boolean) {
  return useQuery({
    queryKey: queryKeys.knowledge,
    queryFn: () => api<KnowledgeDoc[]>('/knowledge'),
    refetchInterval: poll ? 1000 : false,
  })
}

export function useUploadKnowledge() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({
      files,
      docType,
      outcome,
    }: {
      files: File[]
      docType: string
      outcome: string
    }) => {
      const form = new FormData()
      for (const file of files) form.append('files', file)
      form.append('doc_type', docType)
      form.append('outcome', outcome)
      return api<{ job_id: number }>('/knowledge', { method: 'POST', form })
    },
    onSuccess: () => void client.invalidateQueries({ queryKey: queryKeys.knowledge }),
  })
}

export function useUpdateKnowledge() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...body }: { id: number; outcome?: string; doc_type?: string }) =>
      api<KnowledgeDoc>(`/knowledge/${id}`, { method: 'PATCH', body }),
    onSuccess: () => void client.invalidateQueries({ queryKey: queryKeys.knowledge }),
  })
}

export function useDeleteKnowledge() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api<void>(`/knowledge/${id}`, { method: 'DELETE' }),
    onSuccess: () => void client.invalidateQueries({ queryKey: queryKeys.knowledge }),
  })
}

export function useKnowledgeSearch(q: string) {
  return useQuery({
    queryKey: queryKeys.knowledgeSearch(q),
    queryFn: () => api<SearchHit[]>('/knowledge/search', { query: { q } }),
    enabled: q.trim().length >= 2,
  })
}
