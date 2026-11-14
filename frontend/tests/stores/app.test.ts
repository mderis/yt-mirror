import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useAppStore } from '@/stores/app'

import { useToolsStore } from '@/stores/tools'

import { fakeEventStream } from '../helpers/events'
import {
  errorBody,
  firstStart,
  HEALTH,
  healthyApi,
  jsonResponse,
  mockFetch,
} from '../helpers/fetch'

beforeEach(() => setActivePinia(createPinia()))
describe('the app store', () => {
  it('infra: starts in the connecting state with nothing known', () => {
    const store = useAppStore()

    expect(store.status).toBe('connecting')
    expect(store.health).toBeNull()
    expect(store.errorCode).toBeNull()
  })

  it('infra: becomes ready with the versions of the backend', async () => {
    healthyApi()
    const store = useAppStore()

    await store.connect()

    expect(store.status).toBe('ready')
    expect(store.health).toEqual(HEALTH)
    expect(store.errorCode).toBeNull()
  })

  it('R-ER-02: keeps the error code when the backend refuses', async () => {
    mockFetch(() => jsonResponse(errorBody('UNAUTHORIZED'), 401))
    const store = useAppStore()

    await store.connect()

    expect(store.status).toBe('failed')
    expect(store.errorCode).toBe('UNAUTHORIZED')
    expect(store.health).toBeNull()
  })

  it('R-ER-04: fails with the code of its own when the backend cannot be reached', async () => {
    mockFetch(() => Promise.reject(new TypeError('Failed to fetch')))
    const store = useAppStore()

    await store.connect()

    expect(store.status).toBe('failed')
    expect(store.errorCode).toBe('LOCAL_SERVER_UNREACHABLE')
  })

  it('R-ER-02: reports INTERNAL when something other than the API fails', async () => {
    mockFetch(() => new Response('not json', { status: 200 }))
    const store = useAppStore()

    await store.connect()

    expect(store.status).toBe('failed')
    expect(store.errorCode).toBe('INTERNAL')
  })

  it('R-ER-04: can connect again after a failure and forgets the old error', async () => {
    const answers = [jsonResponse(errorBody('INTERNAL'), 500), jsonResponse(HEALTH)]
    healthyApi({ 'GET /api/health': () => answers.shift() as Response })
    const store = useAppStore()
    await store.connect()

    await store.connect()

    expect(store.status).toBe('ready')
    expect(store.errorCode).toBeNull()
    expect(store.health).toEqual(HEALTH)
  })

  it('R-IN-03: connecting loads the tools and learns that the first-run screen is needed', async () => {
    healthyApi({ 'GET /api/tools': jsonResponse(firstStart()) })
    const store = useAppStore()

    await store.connect()

    expect(store.status).toBe('ready')
    expect(useToolsStore().inSetup).toBe(true)
    expect(useToolsStore().tools.map((tool) => tool.name)).toEqual([
      'python',
      'ytdlp',
      'ffmpeg',
      'deno',
    ])
  })

  it('R-FB-03: connecting opens the event stream once, however often it is repeated', async () => {
    const newestStream = fakeEventStream()
    healthyApi()
    const store = useAppStore()

    await store.connect()
    const first = newestStream()
    await store.connect()

    expect(first.url).toBe('/api/events')
    expect(newestStream()).toBe(first)
  })

  it('R-ER-02: a backend that refuses the tools fails the connection with that code', async () => {
    healthyApi({ 'GET /api/tools': jsonResponse(errorBody('INTERNAL'), 500) })
    const store = useAppStore()

    await store.connect()

    expect(store.status).toBe('failed')
    expect(store.errorCode).toBe('INTERNAL')
  })
})
