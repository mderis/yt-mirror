import { describe, expect, it } from 'vitest'

import { api, ApiError, pictures, type EventHandlers } from '@/api/client'

import { appState, channel, CHANNEL_ID, NOW, video } from '../helpers/catalogue'
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

const JSON_HEADERS = { 'Content-Type': 'application/json' }

/** Handlers that hear nothing, except what a test listens for. */
function handlers(changes: Partial<EventHandlers> = {}): EventHandlers {
  const nothing = (): void => undefined
  return {
    toolUpdated: nothing,
    channelUpdated: nothing,
    taskProgress: nothing,
    pauseChanged: nothing,
    reconnected: nothing,
    ...changes,
  }
}

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

    api.openEvents(handlers({ toolUpdated: (event) => seen.push(event) }))
    newestStream().toolUpdated(tool('deno', 'ok'), false)

    expect(newestStream().url).toBe('/api/events')
    expect(seen).toEqual([{ tool: tool('deno', 'ok'), setup_required: false }])
  })

  it('R-FB-03: the stream says when it is connected again after a break, not at first', () => {
    const newestStream = fakeEventStream()
    let reconnects = 0
    const close = api.openEvents(handlers({ reconnected: () => (reconnects += 1) }))

    newestStream().emit('open')
    newestStream().emit('error')
    newestStream().emit('error')
    newestStream().emit('open')
    newestStream().emit('open')
    close()

    expect(reconnects).toBe(1)
    expect(newestStream().closed).toBe(true)
  })

  it('R-FB-03: the event stream hands over a channel, the progress of a listing and the pause', () => {
    const newestStream = fakeEventStream()
    const seen: unknown[] = []
    const progress = {
      channel_id: CHANNEL_ID,
      kind: 'first_listing',
      done: 120,
      total: null,
    } as const
    const pause = { code: 'BOT_CHECK', until: NOW + 900 } as const
    api.openEvents(
      handlers({
        channelUpdated: (changed) => seen.push(changed),
        taskProgress: (made) => seen.push(made),
        pauseChanged: (changed) => seen.push(changed),
      }),
    )

    newestStream().channelUpdated(channel({ title: 'New name' }))
    newestStream().taskProgress(progress)
    newestStream().pauseChanged(pause)
    newestStream().pauseChanged(null)

    expect(seen).toEqual([channel({ title: 'New name' }), progress, pause, null])
  })

  it('R-UI-02: asks for the snapshot of the app and tells which channel is open', async () => {
    const fetchMock = mockApi({
      'GET /api/state': jsonResponse(appState({ channels: [channel()] })),
      'PUT /api/state/open-channel': jsonResponse(appState({ open_channel_id: CHANNEL_ID })),
    })

    const state = await api.getState()
    const remembered = await api.setOpenChannel(CHANNEL_ID)

    expect(state.channels).toEqual([channel()])
    expect(remembered.open_channel_id).toBe(CHANNEL_ID)
    expect(fetchMock).toHaveBeenLastCalledWith('/api/state/open-channel', {
      credentials: 'same-origin',
      method: 'PUT',
      headers: JSON_HEADERS,
      body: JSON.stringify({ channel_id: CHANNEL_ID }),
    })
  })

  it('R-CH-03: looks a channel up, and asks for its video count apart from the preview', async () => {
    const preview = {
      channel_id: CHANNEL_ID,
      title: 'Sample Channel',
      handle: '@sample',
      has_avatar: true,
      existing: false,
      folder: '/Users/sam/Movies/YouTube/Sample Channel',
      video_files: 0,
    }
    const fetchMock = mockApi({
      'POST /api/channels/lookup': jsonResponse(preview),
      [`GET /api/channels/lookup/${CHANNEL_ID}/video-count`]: jsonResponse({ video_count: 57 }),
    })

    const found = await api.lookUpChannel('@sample')
    const count = await api.getPreviewVideoCount(CHANNEL_ID)

    expect(found).toEqual(preview)
    expect(count).toBe(57)
    expect(fetchMock.mock.calls[0]).toEqual([
      '/api/channels/lookup',
      {
        credentials: 'same-origin',
        method: 'POST',
        headers: JSON_HEADERS,
        body: JSON.stringify({ text: '@sample' }),
      },
    ])
  })

  it('R-CH-03: a preview without a count gives none', async () => {
    mockApi({
      [`GET /api/channels/lookup/${CHANNEL_ID}/video-count`]: jsonResponse({ video_count: null }),
    })

    expect(await api.getPreviewVideoCount(CHANNEL_ID)).toBeNull()
  })

  it('R-CH-05: asks for the folder dialog, and adds the channel with what the user chose', async () => {
    const chosen = { folder: '/Volumes/Archive/Sample', video_files: 3 }
    const fetchMock = mockApi({
      'POST /api/folders/choose': jsonResponse(chosen),
      'POST /api/channels': jsonResponse({ channel: channel(), existing: false }, 201),
    })
    const wanted = {
      channel_id: CHANNEL_ID,
      folder: chosen.folder,
      quality: '1080',
      auto_mirror: true,
      mirror_after: NOW,
    } as const

    const folder = await api.chooseFolder()
    const added = await api.addChannel(wanted)

    expect(folder).toEqual(chosen)
    expect(added).toEqual({ channel: channel(), existing: false })
    expect(fetchMock).toHaveBeenLastCalledWith('/api/channels', {
      credentials: 'same-origin',
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(wanted),
    })
  })

  it('R-CH-23: asks for a quick check, a full check and a check of every channel', async () => {
    const fetchMock = mockApi({
      [`POST /api/channels/${CHANNEL_ID}/check`]: jsonResponse(channel({ status: 'checking' })),
      'POST /api/channels/check-all': jsonResponse({ channels: 2 }),
    })

    const checking = await api.checkChannel(CHANNEL_ID, 'quick')
    await api.checkChannel(CHANNEL_ID, 'full')
    const all = await api.checkAllChannels()

    expect(checking.status).toBe('checking')
    expect(all).toEqual({ channels: 2 })
    expect(fetchMock.mock.calls.map(([path, init]) => [path, init?.body])).toEqual([
      [`/api/channels/${CHANNEL_ID}/check`, JSON.stringify({ kind: 'quick' })],
      [`/api/channels/${CHANNEL_ID}/check`, JSON.stringify({ kind: 'full' })],
      ['/api/channels/check-all', undefined],
    ])
  })

  it('R-CH-27: asks to cancel the full check of a channel', async () => {
    mockApi({
      [`POST /api/channels/${CHANNEL_ID}/check/cancel`]: jsonResponse({ cancelled: true }),
    })

    expect(await api.cancelCheck(CHANNEL_ID)).toEqual({ cancelled: true })
  })

  it('R-CH-31: pauses and resumes a channel', async () => {
    const fetchMock = mockApi({
      [`PATCH /api/channels/${CHANNEL_ID}`]: jsonResponse(channel({ paused: true })),
    })

    const paused = await api.setChannelPaused(CHANNEL_ID, true)

    expect(paused.paused).toBe(true)
    expect(fetchMock).toHaveBeenLastCalledWith(`/api/channels/${CHANNEL_ID}`, {
      credentials: 'same-origin',
      method: 'PATCH',
      headers: JSON_HEADERS,
      body: JSON.stringify({ paused: true }),
    })
  })

  it('R-CH-30: opening the folder of a channel has an answer without content', async () => {
    const fetchMock = mockApi({
      [`POST /api/channels/${CHANNEL_ID}/open-folder`]: () => new Response(null, { status: 204 }),
    })

    expect(await api.openChannelFolder(CHANNEL_ID)).toBeUndefined()
    expect(fetchMock).toHaveBeenLastCalledWith(`/api/channels/${CHANNEL_ID}/open-folder`, {
      credentials: 'same-origin',
      method: 'POST',
    })
  })

  it('R-CH-32: removes a channel', async () => {
    const fetchMock = mockApi({
      [`DELETE /api/channels/${CHANNEL_ID}`]: () => new Response(null, { status: 204 }),
    })

    await api.removeChannel(CHANNEL_ID)

    expect(fetchMock).toHaveBeenLastCalledWith(`/api/channels/${CHANNEL_ID}`, {
      credentials: 'same-origin',
      method: 'DELETE',
    })
  })

  it('R-CH-10: asks for the catalogue of a channel', async () => {
    mockApi({
      [`GET /api/channels/${CHANNEL_ID}/videos`]: jsonResponse({ videos: [video(1), video(2)] }),
    })

    expect(await api.getChannelVideos(CHANNEL_ID)).toEqual([video(1), video(2)])
  })

  it('R-ER-05: "Try now" asks to end the pause and gets the app as it is then', async () => {
    const fetchMock = mockApi({ 'POST /api/youtube/try-now': jsonResponse(appState()) })

    const state = await api.tryYouTubeNow()

    expect(state.youtube_pause).toBeNull()
    expect(fetchMock).toHaveBeenLastCalledWith('/api/youtube/try-now', {
      credentials: 'same-origin',
      method: 'POST',
    })
  })

  it('R-CH-16: pictures are loaded from the local server, never from YouTube', () => {
    expect(pictures.avatar(CHANNEL_ID, 3)).toBe(`/api/channels/${CHANNEL_ID}/avatar?v=3`)
    expect(pictures.previewAvatar(CHANNEL_ID)).toBe(`/api/channels/lookup/${CHANNEL_ID}/avatar`)
    expect(pictures.thumbnail('video000001')).toBe('/api/videos/video000001/thumbnail')
    expect(pictures.thumbnail('video000001', 3)).toBe('/api/videos/video000001/thumbnail?v=3')
  })
})
