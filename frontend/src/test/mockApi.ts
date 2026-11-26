import { vi } from 'vitest'

type Handler = unknown

/** Mock global fetch: map `METHOD /api/path` (or `/api/path` for GET) to a JSON body. */
export function mockApi(routes: Record<string, Handler>, status: Record<string, number> = {}) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const href = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
    const url = new URL(href, 'http://localhost')
    const method = (init?.method ?? 'GET').toUpperCase()
    const key = method === 'GET' ? url.pathname : `${method} ${url.pathname}`
    const routeKey = key in routes ? key : `${method} ${url.pathname}`
    if (!(routeKey in routes)) {
      return Promise.resolve(
        new Response(
          JSON.stringify({ error: { code: 'not_found', message: `No mock for ${key}` } }),
          { status: 404 },
        ),
      )
    }
    const handler: unknown = routes[routeKey]
    const body: unknown =
      typeof handler === 'function'
        ? (handler as (u: URL, i?: RequestInit) => unknown)(url, init)
        : handler
    return Promise.resolve(
      new Response(body === undefined ? null : JSON.stringify(body), {
        status: status[key] ?? (body === undefined ? 204 : 200),
        headers: { 'Content-Type': 'application/json' },
      }),
    )
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

export const USER = { id: 1, email: 'admin@example.com', name: 'Admin' }

export const PROJECT = {
  id: 7,
  title: 'HMIS for 25 District Hospitals',
  tender_no: 'DSHM/HMIS/2026/014',
  buyer: 'Deccan State Health Mission',
  deadline: '2099-12-15T09:30:00Z',
  status: 'ready',
  readiness_score: 42,
  outcome: 'unknown',
  competition_rating: null,
  go_no_go: null,
  created_at: '2026-11-26T00:00:00Z',
  counts: { requirements: 3, mandatory: 2, gaps: 1, drafted: 2, approved: 0, fully_compliant: 1 },
  latest_job: null,
  files: [],
  has_package: false,
}
