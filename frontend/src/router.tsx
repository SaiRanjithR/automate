import { Navigate, createBrowserRouter, type RouteObject } from 'react-router'

import { AppShell } from '@/components/common/AppShell'
import { RequireAuth } from '@/features/auth/RequireAuth'
import { LoginPage } from '@/features/auth/LoginPage'
import { LandingPage } from '@/features/landing/LandingPage'
import { CompanyPage } from '@/features/company/CompanyPage'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { KnowledgePage } from '@/features/knowledge/KnowledgePage'
import { PoliciesPage } from '@/features/policies/PoliciesPage'
import { NewProjectPage } from '@/features/projects/NewProjectPage'
import { ProjectPage } from '@/features/projects/ProjectPage'
import { NotFoundPage } from '@/pages/NotFoundPage'

export const routes: RouteObject[] = [
  { path: '/', element: <LandingPage /> },
  { path: '/login', element: <LoginPage /> },
  {
    element: (
      <RequireAuth>
        <AppShell />
      </RequireAuth>
    ),
    children: [
      { path: 'dashboard', element: <DashboardPage /> },
      { path: 'company', element: <CompanyPage /> },
      { path: 'knowledge', element: <KnowledgePage /> },
      { path: 'policies', element: <PoliciesPage /> },
      { path: 'projects/new', element: <NewProjectPage /> },
      { path: 'projects/:id', element: <Navigate to="overview" replace /> },
      { path: 'projects/:id/:tab', element: <ProjectPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]

export function createAppRouter() {
  return createBrowserRouter(routes)
}
