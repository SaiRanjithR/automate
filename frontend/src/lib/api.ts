import type { components } from '@/types/api'

export type Schemas = components['schemas']

export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

type RequestOptions = {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  form?: FormData
  query?: Record<string, string | number | boolean | null | undefined>
}

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api'

export function apiUrl(path: string, query?: RequestOptions['query']): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value))
  }
  const qs = params.toString()
  return `${BASE}${path}${qs ? `?${qs}` : ''}`
}

/** Typed fetch wrapper: JSON in/out, cookies included, errors mapped to ApiError. */
export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, form, query } = options
  const init: RequestInit = { method, credentials: 'include', headers: {} }
  if (form) {
    init.body = form
  } else if (body !== undefined) {
    init.body = JSON.stringify(body)
    init.headers = { 'Content-Type': 'application/json' }
  }
  let response: Response
  try {
    response = await fetch(apiUrl(path, query), init)
  } catch {
    throw new ApiError(0, 'network', 'Cannot reach the BidReady server. Is the backend running?')
  }
  if (response.status === 204) return undefined as T
  const data: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const error = (data as { error?: { code?: string; message?: string } } | null)?.error
    throw new ApiError(
      response.status,
      error?.code ?? 'error',
      error?.message ?? response.statusText,
    )
  }
  return data as T
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return 'Something went wrong'
}
