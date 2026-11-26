import { useQuery } from '@tanstack/react-query'

import { api } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'
import type { Job } from '@/features/projects/types'

export function isJobRunning(job: Job | undefined): boolean {
  return job !== undefined && (job.status === 'queued' || job.status === 'running')
}

/** Polls a background job until it succeeds or fails. */
export function useJob(jobId: number | null | undefined) {
  return useQuery({
    queryKey: queryKeys.job(jobId ?? 0),
    queryFn: () => api<Job>(`/jobs/${jobId}`),
    enabled: Boolean(jobId),
    refetchInterval: (query) => (isJobRunning(query.state.data) || !query.state.data ? 700 : false),
    staleTime: 0,
  })
}

/** Read a numeric counter from a job's counts. */
export function jobCount(job: Job, key: string): number {
  const value = job.counts[key]
  return typeof value === 'number' ? value : 0
}
