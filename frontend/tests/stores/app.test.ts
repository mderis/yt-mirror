import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useAppStore } from '@/stores/app'
import { useChannelsStore } from '@/stores/channels'
import { useToolsStore } from '@/stores/tools'
import { useVideosStore } from '@/stores/videos'

import { appState, channel, CHANNEL_ID, NOW, OTHER_CHANNEL_ID, video } from '../helpers/catalogue'
import { fakeEventStream } from '../helpers/events'
import {
  allToolsReady,
  errorBody,
  firstStart,
  HEALTH,
  healthyApi,
  jsonResponse,
  mockFetch,
  tool,
} from '../helpers/fetch'

/** Let the requests that an event started be answered. */
function settled(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0))
}

const VIDEOS = `GET /api/channels/${CHANNEL_ID}/videos`

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

  it('R-ER-02: a backend that refuses the snapshot fails the connection with that code', async () => {
    healthyApi({ 'GET /api/state': jsonResponse(errorBody('INTERNAL'), 500) })
    const store = useAppStore()

    await store.connect()

    expect(store.status).toBe('failed')
    expect(store.errorCode).toBe('INTERNAL')
  })

  it('R-CH-34: connecting loads the channels of the sidebar', async () => {
    healthyApi({ 'GET /api/state': jsonResponse(appState({ channels: [channel()] })) })

    await useAppStore().connect()

    expect(useChannelsStore().channels).toEqual([channel()])
  })

  it('R-FB-03: a tool event of the stream reaches the tools without a new request', async () => {
    const newestStream = fakeEventStream()
    const fetchMock = healthyApi({ 'GET /api/tools': jsonResponse(firstStart()) })
    await useAppStore().connect()
    const requests = fetchMock.mock.calls.length

    newestStream().toolUpdated(tool('ffmpeg', 'installing', { progress: 0.64 }))

    expect(useToolsStore().tools[2]).toMatchObject({ status: 'installing', progress: 0.64 })
    expect(fetchMock).toHaveBeenCalledTimes(requests)
  })

  it('R-FB-03: a channel event of the stream changes the channel in the sidebar', async () => {
    const newestStream = fakeEventStream()
    healthyApi({ 'GET /api/state': jsonResponse(appState({ channels: [channel()] })) })
    await useAppStore().connect()

    newestStream().channelUpdated(channel({ status: 'checking' }))

    expect(useChannelsStore().channels[0]?.status).toBe('checking')
  })

  it('R-FB-03: when a check of the open channel ended, its catalogue is loaded again', async () => {
    const newestStream = fakeEventStream()
    const answers = [
      jsonResponse({ videos: [video(1)] }),
      jsonResponse({ videos: [video(0), video(1)] }),
    ]
    healthyApi({
      'GET /api/state': jsonResponse(appState({ channels: [channel()] })),
      [VIDEOS]: () => answers.shift() as Response,
    })
    await useAppStore().connect()
    await useVideosStore().open(CHANNEL_ID)

    newestStream().channelUpdated(channel({ last_check_at: NOW, videos: 13, new_videos: 1 }))
    await settled()

    expect(useVideosStore().videos).toEqual([video(0), video(1)])
  })

  it('R-FB-03: a check of another channel does not load the open catalogue again', async () => {
    const newestStream = fakeEventStream()
    const other = channel({ id: OTHER_CHANNEL_ID })
    const fetchMock = healthyApi({
      'GET /api/state': jsonResponse(appState({ channels: [channel(), other] })),
      [VIDEOS]: jsonResponse({ videos: [video(1)] }),
    })
    await useAppStore().connect()
    await useVideosStore().open(CHANNEL_ID)
    const requests = fetchMock.mock.calls.length

    newestStream().channelUpdated({ ...other, last_check_at: NOW })
    newestStream().channelUpdated(channel({ status: 'checking' }))
    await settled()

    expect(fetchMock).toHaveBeenCalledTimes(requests)
  })

  it('R-CH-11: the progress of a listing reaches its channel', async () => {
    const newestStream = fakeEventStream()
    const listing = channel({ first_listed_at: null, last_check_at: null, status: 'checking' })
    healthyApi({ 'GET /api/state': jsonResponse(appState({ channels: [listing] })) })
    await useAppStore().connect()
    const progress = {
      channel_id: CHANNEL_ID,
      kind: 'first_listing',
      done: 120,
      total: null,
    } as const

    newestStream().taskProgress(progress)

    expect(useChannelsStore().channels[0]?.progress).toEqual(progress)
  })

  it('R-ER-05: the pause of YouTube reaches the window when it begins and when it ends', async () => {
    const newestStream = fakeEventStream()
    healthyApi()
    await useAppStore().connect()

    newestStream().pauseChanged({ code: 'BOT_CHECK', until: NOW + 900 })
    const during = useChannelsStore().youtubePause
    newestStream().pauseChanged(null)

    expect(during).toEqual({ code: 'BOT_CHECK', until: NOW + 900 })
    expect(useChannelsStore().youtubePause).toBeNull()
  })

  it('R-FB-03: after a break of the stream the tools, the channels and the open catalogue are loaded again', async () => {
    const newestStream = fakeEventStream()
    const tools = [jsonResponse(firstStart()), jsonResponse(allToolsReady())]
    const states = [
      jsonResponse(appState({ channels: [channel()] })),
      jsonResponse(appState({ channels: [channel({ new_videos: 2 })] })),
    ]
    const catalogues = [jsonResponse({ videos: [video(1)] }), jsonResponse({ videos: [video(0)] })]
    healthyApi({
      'GET /api/tools': () => tools.shift() as Response,
      'GET /api/state': () => states.shift() as Response,
      [VIDEOS]: () => catalogues.shift() as Response,
    })
    await useAppStore().connect()
    await useVideosStore().open(CHANNEL_ID)

    newestStream().emit('open')
    newestStream().breakAndReturn()
    await settled()

    expect(useToolsStore().allReady).toBe(true)
    expect(useChannelsStore().channels[0]?.new_videos).toBe(2)
    expect(useVideosStore().videos).toEqual([video(0)])
  })

  it('R-FB-03: a reload that fails after a break leaves the known state in place', async () => {
    const newestStream = fakeEventStream()
    const refused = (): Response => jsonResponse(errorBody('INTERNAL'), 500)
    const tools = [jsonResponse(firstStart()), refused()]
    const states = [jsonResponse(appState({ channels: [channel()] })), refused()]
    healthyApi({
      'GET /api/tools': () => tools.shift() as Response,
      'GET /api/state': () => states.shift() as Response,
    })
    await useAppStore().connect()

    newestStream().breakAndReturn()
    await settled()

    expect(useToolsStore().tools).toHaveLength(4)
    expect(useChannelsStore().channels).toEqual([channel()])
  })
})
