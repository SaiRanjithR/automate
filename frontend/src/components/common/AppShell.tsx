import { Outlet } from 'react-router'

import { Sidebar } from '@/components/common/Sidebar'

export function AppShell() {
  return (
    <div className="flex min-h-svh">
      <Sidebar />
      <main className="min-w-0 flex-1 px-8 py-6">
        <Outlet />
      </main>
    </div>
  )
}
