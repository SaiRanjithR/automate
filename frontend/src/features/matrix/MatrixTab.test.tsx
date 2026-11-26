import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RouterProvider, createMemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { MatrixTab } from '@/features/matrix/MatrixTab'
import type { RequirementRow } from '@/features/projects/types'
import { mockApi, PROJECT } from '@/test/mockApi'

const base = {
  section_path: '4.2.3 Technical Requirements',
  page: 4,
  keyword: 'shall',
  category: 'hosting',
  criterion_id: 1,
  criterion_name: 'Proposed solution and approach',
  outline_section_id: null,
  version_status: 'unchanged',
  previous_text: null,
  rfp_file_id: 1,
}
const response = {
  confidence: 0.9,
  gap_reason: null,
  approved: false,
  approval_override_reason: null,
  edited_by_user: false,
  needs_review: false,
  model: 'offline',
  updated_at: '2026-11-26T00:00:00Z',
}
const ROWS: RequirementRow[] = [
  {
    ...base,
    id: 11,
    req_code: 'R-4.2-03',
    text: 'The bidder shall guarantee 99.5% monthly uptime.',
    type: 'mandatory',
    source_quote: 'The bidder shall guarantee 99.5% monthly uptime',
    response: {
      ...response,
      id: 101,
      answer: 'We guarantee 99.9% monthly uptime.',
      status: 'fully_compliant',
      citations: [
        {
          chunk_id: 5,
          doc_id: 1,
          filename: 'Profile.pdf',
          page: 2,
          quote: 'We guarantee 99.9% monthly uptime',
        },
      ],
      review_score: 70,
      review_issues: [
        {
          type: 'missing_part',
          message: 'Not addressed: production environment',
          severity: 'high',
        },
      ],
    },
  },
  {
    ...base,
    id: 12,
    req_code: 'R-4.2-07',
    text: 'The solution shall integrate with the state SMS gateway.',
    type: 'mandatory',
    source_quote: 'integrate with the state SMS gateway',
    response: {
      ...response,
      id: 102,
      answer: null,
      status: 'gap',
      citations: [],
      review_score: null,
      review_issues: [],
      gap_reason: 'No evidence',
    },
  },
]

function renderMatrix(path = '/projects/7/matrix') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(
    [
      {
        path: '/projects/:id/:tab',
        element: <MatrixTab project={PROJECT} />,
      },
    ],
    { initialEntries: [path] },
  )
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return router
}

afterEach(() => vi.unstubAllGlobals())

describe('MatrixTab', () => {
  it('shows summary chips and filters by status through the URL', async () => {
    mockApi({
      '/api/projects/7/requirements': (url: URL) => ({
        items: url.searchParams.get('status') === 'gap' ? [ROWS[1]] : ROWS,
        total: 2,
        summary: { total: 2, fully_compliant: 1, gap: 1, pending: 0, approved: 0 },
      }),
      '/api/projects/7/criteria': [],
      '/api/knowledge': [],
    })
    const router = renderMatrix()
    expect(await screen.findByText('R-4.2-03')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /1 gaps/ }))
    await waitFor(() => expect(router.state.location.search).toContain('status=gap'))
    await waitFor(() => expect(screen.queryByText('R-4.2-03')).not.toBeInTheDocument())
  })

  it('requires a reason to approve an answer with high-severity issues', async () => {
    const fetchMock = mockApi({
      '/api/projects/7/requirements': { items: ROWS, total: 2, summary: { total: 2 } },
      '/api/projects/7/criteria': [],
      '/api/knowledge': [],
      '/api/responses/101/history': [],
      'PATCH /api/responses/101': ROWS[0],
    })
    renderMatrix('/projects/7/matrix?row=11')
    const panel = await screen.findByRole('complementary', { name: 'Requirement R-4.2-03' })
    await userEvent.click(within(panel).getByRole('button', { name: /Approve with reason/ }))
    const dialog = await screen.findByRole('dialog')
    const approve = within(dialog).getByRole('button', { name: 'Approve' })
    expect(approve).toBeDisabled()
    await userEvent.type(within(dialog).getByLabelText('Reason'), 'Checked with the delivery team')
    await userEvent.click(approve)
    await waitFor(() => {
      const call = fetchMock.mock.calls.find(([, init]) => init?.method === 'PATCH')
      expect(call).toBeDefined()
      expect(JSON.parse(call?.[1]?.body as string)).toEqual({
        approved: true,
        override_reason: 'Checked with the delivery team',
      })
    })
  })

  it('offers manual entry for gaps', async () => {
    mockApi({
      '/api/projects/7/requirements': { items: ROWS, total: 2, summary: { total: 2 } },
      '/api/projects/7/criteria': [],
      '/api/knowledge': [],
      '/api/responses/102/history': [],
    })
    renderMatrix('/projects/7/matrix?row=12')
    const panel = await screen.findByRole('complementary', { name: 'Requirement R-4.2-07' })
    expect(within(panel).getByText('No evidence found')).toBeInTheDocument()
    expect(within(panel).getByRole('button', { name: 'Approve' })).toBeDisabled()
    await userEvent.click(within(panel).getByRole('button', { name: 'Write manually' }))
    expect(within(panel).getByRole('textbox', { name: 'Answer' })).toBeInTheDocument()
  })
})
