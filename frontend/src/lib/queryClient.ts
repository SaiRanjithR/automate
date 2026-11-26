import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query'

import { ApiError } from '@/lib/api'

function onUnauthorized(error: unknown) {
  if (error instanceof ApiError && error.status === 401 && window.location.pathname !== '/login') {
    queryClient.clear()
    window.location.assign(`/login?next=${encodeURIComponent(window.location.pathname)}`)
  }
}

export const queryClient: QueryClient = new QueryClient({
  queryCache: new QueryCache({ onError: onUnauthorized }),
  mutationCache: new MutationCache({ onError: onUnauthorized }),
  defaultOptions: {
    queries: {
      retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
      staleTime: 10_000,
      refetchOnWindowFocus: false,
    },
  },
})
