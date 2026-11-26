import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingRows } from '@/components/common/LoadingRows'
import { useMe } from '@/features/auth/api'
import { errorMessage } from '@/lib/api'

export function RequireAuth({ children }: { children: ReactNode }) {
  const { data: user, isPending, error, refetch } = useMe()
  const location = useLocation()
  if (isPending) {
    return (
      <div className="p-8">
        <LoadingRows rows={3} label="Checking your session" />
      </div>
    )
  }
  if (error) {
    return (
      <div className="p-8">
        <ErrorState message={errorMessage(error)} onRetry={() => void refetch()} />
      </div>
    )
  }
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(location.pathname)}`} replace />
  return <>{children}</>
}
