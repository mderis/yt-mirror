import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { ApiError } from '@/api/client'
import { useChannelsStore } from '@/stores/channels'

import { appState, channel, CHANNEL_ID, NOW, OTHER_CHANNEL_ID } from '../helpers/catalogue'
import { errorBody, jsonResponse, mockApi } from '../helpers/fetch'

beforeEach(() => setActivePinia(createPinia()))

const other = channel({ id: OTHER_CHANNEL_ID, title: 'Other Channel' })

/** A store that knows two channels, and the fetch mock that answers it. */
async function loaded(answers: Parameters<typeof mockApi>[0] = {}) {
  const fetchMock = mockApi({
    'GET /api/state': jsonResponse(
      appState({ channels: [channel(), other], open_channel_id: CHANNEL_ID }),
    ),
    ...answers,
  })
  const store = useChannelsStore()
  await store.load()
  return { store, fetchMock }
}

describe('the channels store', () => {
  it('R-CH-34: holds the channels of the sidebar in their order', async () => {
    const { store } = await loaded()

    expect(store.channels.map((known) => known.title)).toEqual(['Sample Channel', 'Other Channel'])
    expect(store.byId.get(OTHER_CHANNEL_ID)).toEqual(other)
    expect(store.loaded).toBe(true)
  })

  it('R-UI-01: knows the library and the free space of its disk', async () => {
    const { store } = await loaded()

    expect(store.libraryFolder).toBe('/Users/sam/Movies/YouTube')
    expect(store.disk).toEqual({ name: 'Macintosh HD', free_bytes: 412_000_000_000 })
  })

  it('R-UI-02: knows the channel that was open last, and tells the backend which one is open now', async () => {
    const { store, fetchMock } = await loaded({
      'PUT /api/state/open-channel': jsonResponse(appState()),
    })
    const before = store.lastOpenId

    await store.rememberOpen(OTHER_CHANNEL_ID)

    expect(before).toBe(CHANNEL_ID)
    expect(store.lastOpenId).toBe(OTHER_CHANNEL_ID)
    expect(fetchMock.mock.calls.at(-1)?.[1]?.body).toBe(
      JSON.stringify({ channel_id: OTHER_CHANNEL_ID }),
    )
  })

  it('R-UI-02: before anything is loaded there is no channel and none was open', () => {
    const store = useChannelsStore()

    expect(store.channels).toEqual([])
    expect(store.lastOpenId).toBeNull()
    expect(store.loaded).toBe(false)
  })

  it('R-FB-03: a changed channel takes the place of the one that was known', async () => {
    const { store } = await loaded()

    store.apply(channel({ status: 'checking' }))

    expect(store.channels.map((known) => known.status)).toEqual(['checking', 'up_to_date'])
  })

  it('R-FB-03: a channel that was not known yet is added at the end', async () => {
    const { store } = await loaded()
    const third = channel({ id: 'UCthird000000000000000003' })

    store.apply(third)

    expect(store.channels).toEqual([channel(), other, third])
  })

  it('R-FB-03: a check that ended, other numbers or a first listing say that the catalogue changed', async () => {
    const { store } = await loaded()

    const sameCatalogue = store.apply(channel({ status: 'checking' }))
    const checked = store.apply(channel({ last_check_at: NOW }))
    const moreVideos = store.apply(channel({ last_check_at: NOW, videos: 13 }))
    const listed = store.apply(channel({ last_check_at: NOW, videos: 13, first_listed_at: NOW }))

    expect([sameCatalogue, checked, moreVideos, listed]).toEqual([false, true, true, true])
  })

  it('R-CH-11: the progress of a first listing is kept on its channel', async () => {
    const { store } = await loaded()
    const progress = {
      channel_id: CHANNEL_ID,
      kind: 'first_listing',
      done: 120,
      total: null,
    } as const

    store.applyProgress(progress)

    expect(store.channels.map((known) => known.progress)).toEqual([progress, null])
  })

  it('R-CH-05: adding a channel puts it into the sidebar', async () => {
    const added = channel({ id: 'UCthird000000000000000003', status: 'checking' })
    const { store } = await loaded({
      'POST /api/channels': jsonResponse({ channel: added, existing: false }, 201),
    })

    const answer = await store.add({ channel_id: added.id, auto_mirror: false })

    expect(answer.existing).toBe(false)
    expect(store.channels.at(-1)).toEqual(added)
  })

  it('R-CH-04: adding a channel that exists says so and adds nothing', async () => {
    const { store } = await loaded({
      'POST /api/channels': jsonResponse({ channel: channel(), existing: true }),
    })

    const answer = await store.add({ channel_id: CHANNEL_ID, auto_mirror: false })

    expect(answer.existing).toBe(true)
    expect(store.channels).toHaveLength(2)
  })

  it('R-CH-32: a removed channel leaves the sidebar, and is not the last open one any more', async () => {
    const { store } = await loaded({
      [`DELETE /api/channels/${CHANNEL_ID}`]: () => new Response(null, { status: 204 }),
    })

    await store.remove(CHANNEL_ID)

    expect(store.channels).toEqual([other])
    expect(store.lastOpenId).toBeNull()
  })

  it('R-CH-32: removing another channel than the last open one keeps that one remembered', async () => {
    const { store } = await loaded({
      [`DELETE /api/channels/${OTHER_CHANNEL_ID}`]: () => new Response(null, { status: 204 }),
    })

    await store.remove(OTHER_CHANNEL_ID)

    expect(store.lastOpenId).toBe(CHANNEL_ID)
  })

  it('R-ER-02: a removal that the backend refuses keeps the channel and passes the code on', async () => {
    const { store } = await loaded({
      [`DELETE /api/channels/${CHANNEL_ID}`]: jsonResponse(errorBody('INTERNAL'), 500),
    })

    const error = await store.remove(CHANNEL_ID).catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ code: 'INTERNAL' })
    expect(store.channels).toHaveLength(2)
  })

  it('R-CH-31: pausing and resuming a channel shows at once', async () => {
    const answers = [
      jsonResponse(channel({ paused: true, status: 'paused' })),
      jsonResponse(channel()),
    ]
    const { store } = await loaded({
      [`PATCH /api/channels/${CHANNEL_ID}`]: () => answers.shift() as Response,
    })

    await store.setPaused(CHANNEL_ID, true)
    const paused = store.byId.get(CHANNEL_ID)?.status
    await store.setPaused(CHANNEL_ID, false)

    expect(paused).toBe('paused')
    expect(store.byId.get(CHANNEL_ID)?.status).toBe('up_to_date')
  })

  it('R-CH-23: "Check now" and "Full check" show the channel as being checked at once', async () => {
    const { store, fetchMock } = await loaded({
      [`POST /api/channels/${CHANNEL_ID}/check`]: jsonResponse(channel({ status: 'checking' })),
    })

    await store.check(CHANNEL_ID, 'quick')
    await store.check(CHANNEL_ID, 'full')

    expect(store.byId.get(CHANNEL_ID)?.status).toBe('checking')
    expect(fetchMock.mock.calls.slice(-2).map(([, init]) => init?.body)).toEqual([
      JSON.stringify({ kind: 'quick' }),
      JSON.stringify({ kind: 'full' }),
    ])
  })

  it('R-CH-23: "Check all channels now" asks the backend once for all of them', async () => {
    const { store, fetchMock } = await loaded({
      'POST /api/channels/check-all': jsonResponse({ channels: 2 }),
    })

    await store.checkAll()

    expect(fetchMock.mock.calls.at(-1)?.[0]).toBe('/api/channels/check-all')
  })

  it('R-CH-27: cancelling a full check asks the backend for it', async () => {
    const { store, fetchMock } = await loaded({
      [`POST /api/channels/${CHANNEL_ID}/check/cancel`]: jsonResponse({ cancelled: true }),
    })

    await store.cancelCheck(CHANNEL_ID)

    expect(fetchMock.mock.calls.at(-1)?.[0]).toBe(`/api/channels/${CHANNEL_ID}/check/cancel`)
  })

  it('R-CH-30: "Open folder" asks the backend to show the folder of the channel', async () => {
    const { store, fetchMock } = await loaded({
      [`POST /api/channels/${CHANNEL_ID}/open-folder`]: () => new Response(null, { status: 204 }),
    })

    await store.openFolder(CHANNEL_ID)

    expect(fetchMock.mock.calls.at(-1)?.[0]).toBe(`/api/channels/${CHANNEL_ID}/open-folder`)
  })

  it('R-ER-05: the pause of YouTube is known from the snapshot, and "Try now" ends it', async () => {
    const pause = { code: 'BOT_CHECK', until: NOW + 900 } as const
    mockApi({
      'GET /api/state': jsonResponse(appState({ youtube_pause: pause })),
      'POST /api/youtube/try-now': jsonResponse(appState()),
    })
    const store = useChannelsStore()
    await store.load()
    const during = store.youtubePause

    await store.tryYouTubeNow()

    expect(during).toEqual(pause)
    expect(store.youtubePause).toBeNull()
  })

  it('R-CH-05: knows whether the folder dialog can be shown', async () => {
    mockApi({ 'GET /api/state': jsonResponse(appState({ can_choose_folder: false })) })
    const store = useChannelsStore()

    await store.load()

    expect(store.canChooseFolder).toBe(false)
  })
})
