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

export const api = {
  /** Ask the server for its version and the database schema version. */
  getHealth: (): Promise<Health> => request<Health>('/health'),
}
