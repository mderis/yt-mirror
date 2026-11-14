import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useVideosStore } from '@/stores/videos'

import { CHANNEL_ID, OTHER_CHANNEL_ID, video } from '../helpers/catalogue'
import { errorBody, jsonResponse, mockApi } from '../helpers/fetch'

beforeEach(() => setActivePinia(createPinia()))

const VIDEOS = `GET /api/channels/${CHANNEL_ID}/videos`
const OTHER_VIDEOS = `GET /api/channels/${OTHER_CHANNEL_ID}/videos`

describe('the videos store', () => {
  it('R-CH-10: opening a channel loads its catalogue', async () => {
    mockApi({ [VIDEOS]: jsonResponse({ videos: [video(1), video(2)] }) })
    const store = useVideosStore()

    const opening = store.open(CHANNEL_ID)
    const meanwhile = store.status
    await opening

    expect(meanwhile).toBe('loading')
    expect(store.status).toBe('ready')
    expect(store.channelId).toBe(CHANNEL_ID)
    expect(store.videos).toEqual([video(1), video(2)])
  })

  it('R-CH-10: before a channel is opened there is no catalogue', () => {
    const store = useVideosStore()

    expect(store.status).toBe('idle')
    expect(store.videos).toEqual([])
  })

  it('R-CH-10: the catalogue shown is the one of the open channel, also when an older answer is late', async () => {
    let answerFirst: (response: Response) => void = () => {}
    mockApi({
      [VIDEOS]: () => new Promise<Response>((resolve) => (answerFirst = resolve)),
      [OTHER_VIDEOS]: jsonResponse({ videos: [video(7)] }),
    })
    const store = useVideosStore()

    const first = store.open(CHANNEL_ID)
    await store.open(OTHER_CHANNEL_ID)
    answerFirst(jsonResponse({ videos: [video(1)] }))
    await first

    expect(store.channelId).toBe(OTHER_CHANNEL_ID)
    expect(store.videos).toEqual([video(7)])
  })

  it('R-CH-10: opening another channel does not show the videos of the one before', async () => {
    let answer: (response: Response) => void = () => {}
    mockApi({
      [VIDEOS]: jsonResponse({ videos: [video(1)] }),
      [OTHER_VIDEOS]: () => new Promise<Response>((resolve) => (answer = resolve)),
    })
    const store = useVideosStore()
    await store.open(CHANNEL_ID)

    const opening = store.open(OTHER_CHANNEL_ID)
    const meanwhile = [...store.videos]
    answer(jsonResponse({ videos: [video(7)] }))
    await opening

    expect(meanwhile).toEqual([])
    expect(store.videos).toEqual([video(7)])
  })

  it('R-FB-03: loading again keeps the list on the screen until the new one is there', async () => {
    let answer: (response: Response) => void = () => {}
    const answers = [
      (): Response => jsonResponse({ videos: [video(1)] }),
      (): Promise<Response> => new Promise<Response>((resolve) => (answer = resolve)),
    ]
    mockApi({ [VIDEOS]: () => (answers.shift() as () => Response)() })
    const store = useVideosStore()
    await store.open(CHANNEL_ID)

    const reloading = store.reload()
    const meanwhile = [store.status, [...store.videos]]
    answer(jsonResponse({ videos: [video(0), video(1)] }))
    await reloading

    expect(meanwhile).toEqual(['ready', [video(1)]])
    expect(store.videos).toEqual([video(0), video(1)])
  })

  it('R-ER-02: a catalogue that the backend refuses fails with its code', async () => {
    mockApi({ [VIDEOS]: jsonResponse(errorBody('NOT_FOUND'), 404) })
    const store = useVideosStore()

    await store.open(CHANNEL_ID)

    expect(store.status).toBe('failed')
    expect(store.errorCode).toBe('NOT_FOUND')
  })

  it('R-ER-02: reports INTERNAL when something other than the API fails', async () => {
    mockApi({ [VIDEOS]: () => new Response('not json', { status: 200 }) })
    const store = useVideosStore()

    await store.open(CHANNEL_ID)

    expect(store.errorCode).toBe('INTERNAL')
  })

  it('R-ER-03: a catalogue that failed can be opened again, and the error goes', async () => {
    const answers = [jsonResponse(errorBody('INTERNAL'), 500), jsonResponse({ videos: [video(1)] })]
    mockApi({ [VIDEOS]: () => answers.shift() as Response })
    const store = useVideosStore()
    await store.open(CHANNEL_ID)

    await store.open(CHANNEL_ID)

    expect(store.status).toBe('ready')
    expect(store.errorCode).toBeNull()
  })

  it('R-CH-32: closing forgets the catalogue, as when its channel was removed', async () => {
    mockApi({ [VIDEOS]: jsonResponse({ videos: [video(1)] }) })
    const store = useVideosStore()
    await store.open(CHANNEL_ID)

    store.close()
    await store.reload()

    expect(store.channelId).toBeNull()
    expect(store.videos).toEqual([])
    expect(store.status).toBe('idle')
  })
})
