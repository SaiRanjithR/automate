import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RouterProvider, createMemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AuditTab } from '@/features/audit/AuditTab'
import { mockApi, PROJECT } from '@/test/mockApi'

const finding = (key: string, isNew: boolean, message: string) => ({
  key,
  rule_id: key,
  rule_name: key,
  source: 'file:default.yaml',
  scope: 'requirement',
  severity: 'high',
  message,
  target: { requirement_id: 11, req_code: 'R-4.2-03' },
  new: isNew,
})
const run = (findings: ReturnType<typeof finding>[]) => ({
  id: 1,
  created_at: '2026-11-26T00:00:00Z',
  findings,
  errors: [],
  rules_evaluated: 10,
  resolved: 0,
  new_count: findings.filter((f) => f.new).length,
  counts: { high: findings.length, medium: 0, low: 0 },
})

function renderTab() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter([{ path: '*', element: <AuditTab project={PROJECT} /> }])
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

afterEach(() => vi.unstubAllGlobals())

describe('AuditTab', () => {
  it('re-runs the audit and highlights new exceptions', async () => {
    mockApi({
      '/api/projects/7/audit': run([finding('old-rule', false, 'Existing exception')]),
      'POST /api/projects/7/audit': run([
        finding('old-rule', false, 'Existing exception'),
        finding('judge-rule', true, 'R-4.2-03: newly flagged by the judge rule'),
      ]),
    })
    renderTab()
    expect(await screen.findByText('Existing exception')).toBeInTheDocument()
    expect(screen.queryByText('NEW')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Re-run audit/ }))
    const newItem = (await screen.findByText('R-4.2-03: newly flagged by the judge rule')).closest(
      'li',
    )
    expect(newItem).not.toBeNull()
    expect(within(newItem as HTMLElement).getByText('NEW')).toBeInTheDocument()
    expect(within(newItem as HTMLElement).getByRole('link', { name: 'R-4.2-03' })).toHaveAttribute(
      'href',
      '/projects/7/matrix?row=11',
    )

    await userEvent.click(screen.getByLabelText('Only new exceptions'))
    expect(screen.queryByText('Existing exception')).not.toBeInTheDocument()
  })

  it('invites a first run when there is no audit yet', async () => {
    mockApi({ '/api/projects/7/audit': null })
    renderTab()
    expect(await screen.findByText('No audit yet')).toBeInTheDocument()
  })
})
