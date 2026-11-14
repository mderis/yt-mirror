import { describe, expect, it } from 'vitest'

import { api, ApiError } from '@/api/client'

import { fakeEventStream } from '../helpers/events'
import {
  allToolsReady,
  errorBody,
  HEALTH,
  jsonResponse,
  mockApi,
  mockFetch,
  tool,
} from '../helpers/fetch'

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

  it('R-IN-03: asks for the tools and for the installation of one', async () => {
    const fetchMock = mockApi({
      'GET /api/tools': jsonResponse(allToolsReady()),
      'POST /api/tools/deno/install': jsonResponse(tool('deno', 'installing', { progress: 0 })),
    })

    const tools = await api.getTools()
    const started = await api.installTool('deno')

    expect(tools.tools).toHaveLength(4)
    expect(started.status).toBe('installing')
    expect(fetchMock).toHaveBeenLastCalledWith('/api/tools/deno/install', {
      credentials: 'same-origin',
      method: 'POST',
    })
  })

  it('R-FB-03: the event stream hands over the data of a tool event', () => {
    const newestStream = fakeEventStream()
    const seen: unknown[] = []

    api.openEvents({ toolUpdated: (event) => seen.push(event), reconnected: () => undefined })
    newestStream().toolUpdated(tool('deno', 'ok'), false)

    expect(newestStream().url).toBe('/api/events')
    expect(seen).toEqual([{ tool: tool('deno', 'ok'), setup_required: false }])
  })

  it('R-FB-03: the stream says when it is connected again after a break, not at first', () => {
    const newestStream = fakeEventStream()
    let reconnects = 0
    const close = api.openEvents({
      toolUpdated: () => undefined,
      reconnected: () => (reconnects += 1),
    })

    newestStream().emit('open')
    newestStream().emit('error')
    newestStream().emit('error')
    newestStream().emit('open')
    newestStream().emit('open')
    close()

    expect(reconnects).toBe(1)
    expect(newestStream().closed).toBe(true)
  })
})
