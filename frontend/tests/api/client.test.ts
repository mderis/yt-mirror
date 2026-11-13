import { describe, expect, it } from 'vitest'

import { api, ApiError } from '@/api/client'

import { errorBody, HEALTH, jsonResponse, mockFetch } from '../helpers/fetch'

describe('the API client', () => {
  it('R-PL-10: calls the API on the same origin and sends the session cookie', async () => {
    const fetchMock = mockFetch(() => jsonResponse(HEALTH))

    const health = await api.getHealth()

    expect(health).toEqual(HEALTH)
    expect(fetchMock).toHaveBeenCalledWith('/api/health', { credentials: 'same-origin' })
  })

  it('R-ER-02: turns an error response into an ApiError with its stable code', async () => {
    mockFetch(() => jsonResponse(errorBody('UNAUTHORIZED', { why: 'no cookie' }), 401))

    const error = await api.getHealth().catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({
      status: 401,
      code: 'UNAUTHORIZED',
      details: { why: 'no cookie' },
    })
  })

  it('R-ER-02: reports INTERNAL when an error response cannot be read', async () => {
    mockFetch(() => new Response('<html>Bad Gateway</html>', { status: 502 }))

    const error = await api.getHealth().catch((caught: unknown) => caught)

    expect(error).toMatchObject({ status: 502, code: 'INTERNAL', details: {} })
  })

  it('R-ER-04: reports an unreachable server under its own error code', async () => {
    mockFetch(() => Promise.reject(new TypeError('Failed to fetch')))

    const error = await api.getHealth().catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 0, code: 'LOCAL_SERVER_UNREACHABLE', details: {} })
  })
})
