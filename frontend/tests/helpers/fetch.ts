/** Replaces the global fetch with canned answers, for tests of the API client and stores. */
import { vi, type Mock } from 'vitest'

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

export function mockFetch(answer: () => Response | Promise<Response>): Mock<typeof fetch> {
  const mock = vi.fn<typeof fetch>(() => Promise.resolve(answer()))
  vi.stubGlobal('fetch', mock)
  return mock
}

export const HEALTH = { status: 'ok', version: '1.2.3', schema_version: '0002' } as const

export function errorBody(code: string, details: Record<string, string> = {}): unknown {
  return { error: { code, message: 'A technical sentence.', details } }
}
