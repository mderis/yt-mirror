/**
 * The thin typed client of the yt-mirror API (docs/ARCHITECTURE.md section 8).
 *
 * This is the only module that calls fetch. Stores use it, components never
 * do. The types come from schema.d.ts, which is generated from the OpenAPI
 * schema with `npm run gen:api` and never edited by hand.
 *
 * The session cookie set by the first URL travels with every request
 * (docs/DECISIONS.md D-038), so no token appears in this code.
 */
import type { components } from './schema'

export type Health = components['schemas']['HealthResponse']
/** The state of one tool the app needs (R-IN-03). */
export type Tool = components['schemas']['Tool']
export type ToolName = components['schemas']['ToolName']
export type ToolsAnswer = components['schemas']['ToolsResponse']
export type ToolUpdated = components['schemas']['ToolUpdatedEvent']
/** Every error code the app knows, from backend/ytmirror/core/errors.py through the API schema. */
export type ErrorCode = components['schemas']['ErrorCode']
type ErrorResponse = components['schemas']['ErrorResponse']

const API_PREFIX = '/api'
const UNREADABLE: ErrorCode = 'INTERNAL'
/** The one code the window raises itself: its own server did not answer at all (R-ER-04). */
const UNREACHABLE: ErrorCode = 'LOCAL_SERVER_UNREACHABLE'

/** A failed API call, with the stable error code of docs/LOGGING.md section 4. */
export class ApiError extends Error {
  /** The HTTP status, or 0 when the server could not be reached. */
  readonly status: number
  /** The error code. */
  readonly code: ErrorCode
  /** Extra facts for the technical details. */
  readonly details: Readonly<Record<string, string>>

  constructor(status: number, code: ErrorCode, details: Record<string, string> = {}) {
    super(code)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_PREFIX}${path}`, { credentials: 'same-origin', ...init })
  } catch {
    throw new ApiError(0, UNREACHABLE)
  }
  if (!response.ok) {
    throw await toApiError(response)
  }
  return (await response.json()) as T
}

async function toApiError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as ErrorResponse
    return new ApiError(response.status, body.error.code, body.error.details)
  } catch {
    return new ApiError(response.status, UNREADABLE)
  }
}

/** What a listener of the event stream wants to hear about. */
export interface EventHandlers {
  /** The state of a tool changed, or its download made progress. */
  toolUpdated: (event: ToolUpdated) => void
  /** The stream is connected again after a break: events may have been missed. */
  reconnected: () => void
}

/**
 * Open the event stream of this window (docs/ARCHITECTURE.md section 7.6).
 *
 * The browser reconnects by itself after a break. Returns a function that closes the stream.
 */
function openEvents(handlers: EventHandlers): () => void {
  const source = new EventSource(`${API_PREFIX}/events`)
  let broken = false
  source.addEventListener('tool.updated', (message) => {
    handlers.toolUpdated(JSON.parse((message as MessageEvent<string>).data) as ToolUpdated)
  })
  source.addEventListener('error', () => {
    broken = true
  })
  source.addEventListener('open', () => {
    if (broken) {
      broken = false
      handlers.reconnected()
    }
  })
  return () => source.close()
}

export const api = {
  /** Ask the server for its version and the database schema version. */
  getHealth: (): Promise<Health> => request<Health>('/health'),
  /** Ask for the state of every tool, and whether the first-run screen is needed. */
  getTools: (): Promise<ToolsAnswer> => request<ToolsAnswer>('/tools'),
  /** Start installing a tool. The answer is its state right after the start. */
  installTool: (name: ToolName): Promise<Tool> =>
    request<Tool>(`/tools/${name}/install`, { method: 'POST' }),
  openEvents,
}
