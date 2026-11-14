import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useToolsStore } from '@/stores/tools'

import { fakeEventStream } from '../helpers/events'
import { allToolsReady, errorBody, firstStart, jsonResponse, mockApi, tool } from '../helpers/fetch'

beforeEach(() => setActivePinia(createPinia()))

describe('the tools store', () => {
  it('R-IN-03: loads the tools in the order of the first-run screen and enters setup', async () => {
    mockApi({ 'GET /api/tools': jsonResponse(firstStart()) })
    const store = useToolsStore()

    await store.load()

    expect(store.tools.map((known) => [known.name, known.status])).toEqual([
      ['python', 'ok'],
      ['ytdlp', 'ok'],
      ['ffmpeg', 'missing'],
      ['deno', 'missing'],
    ])
    expect(store.inSetup).toBe(true)
    expect(store.allReady).toBe(false)
    expect(store.troubled.map((known) => known.name)).toEqual(['ffmpeg', 'deno'])
  })

  it('R-IN-04: with every tool in place there is no setup and nothing to fix', async () => {
    mockApi({ 'GET /api/tools': jsonResponse(allToolsReady()) })
    const store = useToolsStore()

    await store.load()

    expect(store.inSetup).toBe(false)
    expect(store.allReady).toBe(true)
    expect(store.troubled).toEqual([])
  })

  it('R-IN-03: before the tools are known, nothing counts as ready', () => {
    const store = useToolsStore()

    expect(store.allReady).toBe(false)
    expect(store.installing).toBe(false)
  })

  it('R-IN-03: installing a tool asks the backend and shows the tool as installing', async () => {
    const fetchMock = mockApi({
      'GET /api/tools': jsonResponse(firstStart()),
      'POST /api/tools/ffmpeg/install': jsonResponse(tool('ffmpeg', 'installing', { progress: 0 })),
    })
    const store = useToolsStore()
    await store.load()

    await store.install('ffmpeg')

    expect(fetchMock).toHaveBeenLastCalledWith('/api/tools/ffmpeg/install', {
      credentials: 'same-origin',
      method: 'POST',
    })
    expect(store.tools[2]).toMatchObject({ name: 'ffmpeg', status: 'installing', progress: 0 })
    expect(store.installing).toBe(true)
  })

  it('R-FB-03: a tool that is installed before the request is answered stays installed', async () => {
    const newestStream = fakeEventStream()
    let answer: (response: Response) => void = () => {}
    mockApi({
      'GET /api/tools': jsonResponse(firstStart()),
      'POST /api/tools/deno/install': () => new Promise<Response>((resolve) => (answer = resolve)),
    })
    const store = useToolsStore()
    await store.load()
    store.listen()

    const installing = store.install('deno')
    newestStream().toolUpdated(tool('deno', 'installing', { progress: 0 }))
    newestStream().toolUpdated(tool('deno', 'ok', { version: '2.9.8', source: 'deno' }))
    answer(jsonResponse(tool('deno', 'installing', { progress: 0 })))
    await installing

    expect(store.tools[3]).toMatchObject({ status: 'ok', version: '2.9.8' })
  })

  it('R-FB-03: a failure that arrives on the stream is not replaced by a late refusal', async () => {
    const newestStream = fakeEventStream()
    let answer: (response: Response) => void = () => {}
    mockApi({
      'GET /api/tools': jsonResponse(firstStart()),
      'POST /api/tools/deno/install': () => new Promise<Response>((resolve) => (answer = resolve)),
    })
    const store = useToolsStore()
    await store.load()
    store.listen()

    const installing = store.install('deno')
    newestStream().toolUpdated(tool('deno', 'failed', { error_code: 'DISK_FULL' }))
    answer(jsonResponse(errorBody('INTERNAL'), 500))
    await installing

    expect(store.tools[3]?.error_code).toBe('DISK_FULL')
  })

  it('R-ER-02: a refused installation shows as a failed tool with the error code', async () => {
    mockApi({
      'GET /api/tools': jsonResponse(firstStart()),
      'POST /api/tools/deno/install': jsonResponse(errorBody('INVALID_REQUEST'), 422),
    })
    const store = useToolsStore()
    await store.load()

    await store.install('deno')

    expect(store.tools[3]).toMatchObject({
      name: 'deno',
      status: 'failed',
      error_code: 'INVALID_REQUEST',
    })
  })

  it('R-ER-04: an installation that cannot reach the backend fails with the window code', async () => {
    mockApi({ 'GET /api/tools': jsonResponse(firstStart()) })
    const store = useToolsStore()
    await store.load()

    await store.install('deno')

    expect(store.tools[3]?.error_code).toBe('LOCAL_SERVER_UNREACHABLE')
  })

  it('R-IN-03: installing a tool the store does not know changes nothing', async () => {
    mockApi({})
    const store = useToolsStore()

    await store.install('deno')

    expect(store.tools).toEqual([])
  })

  it('R-FB-03: an event of the stream updates the tool without a new request', async () => {
    const newestStream = fakeEventStream()
    const fetchMock = mockApi({ 'GET /api/tools': jsonResponse(firstStart()) })
    const store = useToolsStore()
    await store.load()
    store.listen()

    newestStream().toolUpdated(tool('ffmpeg', 'installing', { progress: 0.64 }))
    newestStream().toolUpdated(tool('deno', 'ok', { version: '2.9.8', source: 'deno' }))

    expect(store.tools[2]).toMatchObject({ status: 'installing', progress: 0.64 })
    expect(store.tools[3]).toMatchObject({ status: 'ok', version: '2.9.8', source: 'deno' })
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('R-FB-03: an event about a tool that is not known yet adds it', () => {
    const newestStream = fakeEventStream()
    const store = useToolsStore()
    store.listen()

    newestStream().toolUpdated(tool('deno', 'missing'))

    expect(store.tools.map((known) => known.name)).toEqual(['deno'])
  })

  it('R-FB-03: after a break of the stream the tools are loaded again', async () => {
    const newestStream = fakeEventStream()
    const answers = [jsonResponse(firstStart()), jsonResponse(allToolsReady())]
    const fetchMock = mockApi({ 'GET /api/tools': () => answers.shift() as Response })
    const store = useToolsStore()
    await store.load()
    store.listen()

    newestStream().emit('open')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    newestStream().emit('error')
    newestStream().emit('open')
    await Promise.resolve()
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(store.allReady).toBe(true)
  })

  it('R-FB-03: a reload that fails after a break leaves the known state in place', async () => {
    const newestStream = fakeEventStream()
    const answers = [jsonResponse(firstStart()), jsonResponse(errorBody('INTERNAL'), 500)]
    mockApi({ 'GET /api/tools': () => answers.shift() as Response })
    const store = useToolsStore()
    await store.load()
    store.listen()

    newestStream().emit('error')
    newestStream().emit('open')
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(store.tools).toHaveLength(4)
  })

  it('infra: listening twice opens one stream, and stopping closes it', () => {
    const newestStream = fakeEventStream()
    const store = useToolsStore()

    store.listen()
    const first = newestStream()
    store.listen()
    store.stopListening()
    store.stopListening()

    expect(newestStream()).toBe(first)
    expect(first.closed).toBe(true)
  })

  it('R-IN-03: the first-run screen installs one tool at a time, in order', async () => {
    const fetchMock = mockApi({
      'GET /api/tools': jsonResponse(firstStart()),
      'POST /api/tools/ffmpeg/install': jsonResponse(tool('ffmpeg', 'installing', { progress: 0 })),
    })
    const store = useToolsStore()
    await store.load()

    await store.installNextMissing()
    await store.installNextMissing()

    expect(fetchMock.mock.calls.map(([path]) => path)).toEqual([
      '/api/tools',
      '/api/tools/ffmpeg/install',
    ])
  })

  it('R-IN-03: a failed tool waits for "Try again" while the next one is started', async () => {
    const answer = firstStart()
    answer.tools[2] = tool('ffmpeg', 'failed', { error_code: 'NETWORK_UNREACHABLE' })
    const fetchMock = mockApi({
      'GET /api/tools': jsonResponse(answer),
      'POST /api/tools/deno/install': jsonResponse(tool('deno', 'installing', { progress: 0 })),
    })
    const store = useToolsStore()
    await store.load()

    await store.installNextMissing()

    expect(fetchMock.mock.calls.at(-1)?.[0]).toBe('/api/tools/deno/install')
  })

  it('R-IN-04: a tool the app cannot install by itself is never started', async () => {
    const answer = allToolsReady()
    answer.tools[1] = tool('ytdlp', 'missing')
    const fetchMock = mockApi({ 'GET /api/tools': jsonResponse(answer) })
    const store = useToolsStore()
    await store.load()

    await store.installNextMissing()

    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('R-IN-03: leaving the first-run screen is remembered for this window', async () => {
    mockApi({ 'GET /api/tools': jsonResponse(firstStart()) })
    const store = useToolsStore()
    await store.load()

    store.finishSetup()

    expect(store.inSetup).toBe(false)
  })
})
