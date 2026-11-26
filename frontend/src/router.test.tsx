import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { RouterProvider, createMemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { TooltipProvider } from '@/components/ui/tooltip'
import { routes } from '@/router'
import { mockApi, PROJECT, USER } from '@/test/mockApi'

vi.mock('@/features/landing/HeroScene', () => ({ default: () => <div data-testid="hero-scene" /> }))

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <TooltipProvider>
        <RouterProvider router={router} />
      </TooltipProvider>
    </QueryClientProvider>,
  )
  return router
}

const COMMON = {
  '/api/auth/me': USER,
  '/api/projects': [],
  '/api/projects/7': PROJECT,
  '/api/projects/7/rules': {},
  '/api/projects/7/criteria': [],
  '/api/projects/7/go-no-go': {
    decision: 'go',
    score: 0.8,
    factors: { fit: 1, risk: 1, resources: 1, competition: 0.5 },
    reasons: ['ok'],
    eligibility_failed: [],
    drafted: true,
  },
  '/api/projects/7/win-themes': [],
  '/api/projects/7/requirements': { items: [], total: 0, summary: { total: 0 } },
  '/api/company': { id: 1, legal_name: 'Acme', turnover: [], certifications: [] },
  '/api/knowledge': [],
}

afterEach(() => vi.unstubAllGlobals())

describe('routes', () => {
  it.each([
    ['/dashboard', 'Dashboard'],
    ['/company', 'Company profile'],
    ['/knowledge', 'Knowledge base'],
    ['/projects/new', 'New project'],
    ['/projects/7/overview', PROJECT.title],
  ])('renders %s inside the app shell', async (path, heading) => {
    mockApi(COMMON)
    renderAt(path)
    expect(await screen.findByRole('heading', { level: 1, name: heading })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Main' })).toBeInTheDocument()
  })

  it('redirects to login when signed out', async () => {
    mockApi(
      {
        ...COMMON,
        '/api/auth/me': { error: { code: 'unauthorized', message: 'Sign in required' } },
      },
      { '/api/auth/me': 401 },
    )
    const router = renderAt('/company')
    expect(
      await screen.findByText('Sign in', { selector: '[data-slot="card-title"]' }),
    ).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
    expect(screen.queryByRole('navigation', { name: 'Main' })).not.toBeInTheDocument()
  })

  it('redirects a project without a valid tab to overview', async () => {
    mockApi(COMMON)
    const router = renderAt('/projects/7/unknown')
    await screen.findByRole('heading', { level: 1, name: PROJECT.title })
    expect(router.state.location.pathname).toBe('/projects/7/overview')
  })

  it('shows the public landing page at / without the app shell', async () => {
    mockApi(
      {
        ...COMMON,
        '/api/auth/me': { error: { code: 'unauthorized', message: 'Sign in required' } },
      },
      { '/api/auth/me': 401 },
    )
    renderAt('/')
    expect(
      await screen.findByRole('heading', {
        level: 1,
        name: /Turn any tender into a ready-to-sign bid/,
      }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Main' })).not.toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /Get started/ })[0]).toHaveAttribute(
      'href',
      '/login?next=%2Fdashboard',
    )
    expect(await screen.findByTestId('hero-scene')).toBeInTheDocument()
  })

  it('offers the dashboard on the landing page when signed in', async () => {
    mockApi(COMMON)
    renderAt('/')
    expect((await screen.findAllByRole('link', { name: /Open dashboard/ }))[0]).toHaveAttribute(
      'href',
      '/dashboard',
    )
  })

  it('shows not found for unknown pages', async () => {
    mockApi(COMMON)
    renderAt('/nope')
    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument()
  })
})
