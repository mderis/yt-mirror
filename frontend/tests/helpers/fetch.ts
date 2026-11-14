/** Replaces the global fetch with canned answers, for tests of the API client and stores. */
import { vi, type Mock } from 'vitest'

import type { Tool, ToolName, ToolsAnswer } from '@/api/client'

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

export const HEALTH = { status: 'ok', version: '1.2.3', schema_version: '0003' } as const

export function errorBody(code: string, details: Record<string, string> = {}): unknown {
  return { error: { code, message: 'A technical sentence.', details } }
}

/** Returns a tool in a given state. Downloaded tools are installable. */
export function tool(name: ToolName, status: Tool['status'], changes: Partial<Tool> = {}): Tool {
  const downloaded = name === 'ffmpeg' || name === 'deno'
  return {
    name,
    status,
    version: status === 'ok' ? '1.0' : null,
    source: status === 'ok' && downloaded ? 'a-source' : null,
    progress: null,
    error_code: null,
    installable: downloaded,
    ...changes,
  }
}

/** The answer of `/api/tools` on a Mac where every tool is in place. */
export function allToolsReady(): ToolsAnswer {
  return {
    tools: [tool('python', 'ok'), tool('ytdlp', 'ok'), tool('ffmpeg', 'ok'), tool('deno', 'ok')],
    setup_required: false,
  }
}

/** The answer of `/api/tools` at the very first start. */
export function firstStart(): ToolsAnswer {
  return {
    tools: [
      tool('python', 'ok'),
      tool('ytdlp', 'ok'),
      tool('ffmpeg', 'missing'),
      tool('deno', 'missing'),
    ],
    setup_required: true,
  }
}

type Answer = Response | (() => Response | Promise<Response>)

/**
 * Replaces fetch with one answer per API path, for example `GET /api/tools`.
 * A path without an answer fails the test.
 */
export function mockApi(answers: Record<string, Answer>): Mock<typeof fetch> {
  const mock = vi.fn<typeof fetch>((input, init) => {
    const key = `${init?.method ?? 'GET'} ${String(input)}`
    const answer = answers[key]
    if (answer === undefined) {
      return Promise.reject(new Error(`The test gave no answer for ${key}`))
    }
    return Promise.resolve(typeof answer === 'function' ? answer() : answer.clone())
  })
  vi.stubGlobal('fetch', mock)
  return mock
}

/** The answers of a healthy backend on a Mac where every tool is in place. */
export function healthyApi(changes: Record<string, Answer> = {}): Mock<typeof fetch> {
  return mockApi({
    'GET /api/health': jsonResponse(HEALTH),
    'GET /api/tools': jsonResponse(allToolsReady()),
    ...changes,
  })
}
