import { fireEvent, screen, waitFor, within } from '@testing-library/vue'
import { describe, expect, it } from 'vitest'

import App from '@/App.vue'

import { fakeEventStream } from '../helpers/events'
import { allToolsReady, firstStart, healthyApi, jsonResponse, tool } from '../helpers/fetch'
import { renderWithApp } from '../helpers/render'

function row(name: string): HTMLElement {
  const found = document.querySelector<HTMLElement>(`[data-tool="${name}"]`)
  if (!found) {
    throw new Error(`No row for ${name}`)
  }
  return found
}

function firstRun(changes: Parameters<typeof healthyApi>[0] = {}): ReturnType<typeof healthyApi> {
  return healthyApi({
    'GET /api/tools': jsonResponse(firstStart()),
    'POST /api/tools/ffmpeg/install': jsonResponse(tool('ffmpeg', 'installing', { progress: 0 })),
    'POST /api/tools/deno/install': jsonResponse(tool('deno', 'installing', { progress: 0 })),
    ...changes,
  })
}

describe('the first-run screen', () => {
  it('R-IN-03: on first start it shows the four tools the app needs', async () => {
    firstRun()

    renderWithApp(App)

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Getting yt-mirror ready' }),
    ).toBeTruthy()
    expect(
      screen.getByText(/nothing is installed or changed anywhere else on your Mac/),
    ).toBeTruthy()
    expect(
      [...document.querySelectorAll('[data-tool]')].map((item) => item.getAttribute('data-tool')),
    ).toEqual(['python', 'ytdlp', 'ffmpeg', 'deno'])
    expect(row('python').textContent).toContain('Python environment')
    expect(row('python').textContent).toContain('Installed')
    expect(row('ytdlp').textContent).toContain('The YouTube download engine')
    expect(screen.getByText('About 120 MB in total. This only happens once.')).toBeTruthy()
    expect(screen.queryByRole('heading', { name: 'Mirror your first channel' })).toBeNull()
  })

  it('R-IN-03: it downloads the first missing tool at once and lets the next one wait', async () => {
    const fetchMock = firstRun()

    renderWithApp(App)

    await waitFor(() => expect(row('ffmpeg').getAttribute('data-status')).toBe('installing'))
    expect(row('ffmpeg').textContent).toContain('Downloading 0%')
    expect(row('deno').textContent).toContain('Waiting')
    expect(fetchMock.mock.calls.map(([path]) => path)).toEqual([
      '/api/health',
      '/api/tools',
      '/api/state',
      '/api/tools/ffmpeg/install',
    ])
  })

  it('R-IN-03: the download shows its progress as a bar and as a number', async () => {
    const newestStream = fakeEventStream()
    firstRun()
    renderWithApp(App)
    await waitFor(() => expect(row('ffmpeg').getAttribute('data-status')).toBe('installing'))

    newestStream().toolUpdated(tool('ffmpeg', 'installing', { progress: 0.64 }))

    await waitFor(() => expect(row('ffmpeg').textContent).toContain('Downloading 64%'))
    const bar = within(row('ffmpeg')).getByRole('progressbar', { name: 'Progress of ffmpeg' })
    expect(bar.getAttribute('aria-valuenow')).toBe('64')
  })

  it('R-IN-03: progress of an unknown size is shown without a number', async () => {
    const newestStream = fakeEventStream()
    firstRun()
    renderWithApp(App)
    await waitFor(() => expect(row('ffmpeg').getAttribute('data-status')).toBe('installing'))

    newestStream().toolUpdated(tool('ffmpeg', 'installing', { progress: null }))

    await waitFor(() => expect(row('ffmpeg').textContent).toContain('Downloading'))
    expect(row('ffmpeg').textContent).not.toContain('%')
  })

  it('R-IN-03: when one tool is installed, the next one starts by itself', async () => {
    const newestStream = fakeEventStream()
    const fetchMock = firstRun()
    renderWithApp(App)
    await waitFor(() => expect(row('ffmpeg').getAttribute('data-status')).toBe('installing'))

    newestStream().toolUpdated(tool('ffmpeg', 'ok', { version: '9.0.2', source: 'martin-riedl' }))

    await waitFor(() => expect(row('deno').getAttribute('data-status')).toBe('installing'))
    expect(row('ffmpeg').textContent).toContain('Installed')
    expect(fetchMock.mock.calls.at(-1)?.[0]).toBe('/api/tools/deno/install')
  })

  it('R-IN-03: a failed step says why in plain words and offers a retry', async () => {
    const newestStream = fakeEventStream()
    const fetchMock = firstRun()
    renderWithApp(App)
    await waitFor(() => expect(row('ffmpeg').getAttribute('data-status')).toBe('installing'))

    newestStream().toolUpdated(tool('ffmpeg', 'failed', { error_code: 'NETWORK_UNREACHABLE' }))

    await waitFor(() =>
      expect(row('ffmpeg').textContent).toContain('Download failed: no internet connection'),
    )
    await waitFor(() => expect(row('deno').getAttribute('data-status')).toBe('installing'))
    await fireEvent.click(within(row('ffmpeg')).getByRole('button', { name: 'Try again' }))
    await waitFor(() => expect(row('ffmpeg').getAttribute('data-status')).toBe('installing'))
    expect(
      fetchMock.mock.calls.filter(([path]) => path === '/api/tools/ffmpeg/install'),
    ).toHaveLength(2)
  })

  it.each([
    ['CHECKSUM_MISMATCH', 'the downloaded file was damaged'],
    ['DISK_FULL', 'the disk is full'],
    ['TOOL_MISSING', 'the tool does not work on this Mac'],
    ['INTERNAL', 'an unexpected problem'],
    ['NOT_FOUND', 'an unexpected problem'],
  ] as const)('R-ER-02: a failure with the code %s reads "%s"', async (code, words) => {
    const answer = firstStart()
    answer.tools[2] = tool('ffmpeg', 'failed', { error_code: code })
    firstRun({ 'GET /api/tools': jsonResponse(answer) })

    renderWithApp(App)

    await waitFor(() => expect(row('ffmpeg').textContent).toContain(`Download failed: ${words}`))
  })

  it('R-IN-03: "Continue" is possible only once every tool is in order', async () => {
    const newestStream = fakeEventStream()
    firstRun()
    renderWithApp(App)
    const button = (await screen.findByRole('button', { name: 'Continue' })) as HTMLButtonElement
    expect(button.disabled).toBe(true)

    newestStream().toolUpdated(tool('ffmpeg', 'ok'))
    newestStream().toolUpdated(tool('deno', 'ok'), false)
    await waitFor(() => expect(button.disabled).toBe(false))
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Getting yt-mirror ready')
    await fireEvent.click(button)

    expect(await screen.findByRole('heading', { name: 'Mirror your first channel' })).toBeTruthy()
    expect(screen.queryByText('Getting yt-mirror ready')).toBeNull()
  })

  it('R-IN-04: a tool the app cannot install says how it gets repaired', async () => {
    const answer = firstStart()
    answer.tools[1] = tool('ytdlp', 'missing')
    firstRun({ 'GET /api/tools': jsonResponse(answer) })

    renderWithApp(App)

    await waitFor(() =>
      expect(row('ytdlp').textContent).toContain(
        'Missing. Quit yt-mirror and open it again to repair it.',
      ),
    )
    expect(within(row('ytdlp')).queryByRole('button')).toBeNull()
    expect(row('ytdlp').textContent).not.toContain('Waiting')
  })

  it('R-IN-03: with every tool in place there is no first-run screen', async () => {
    healthyApi({ 'GET /api/tools': jsonResponse(allToolsReady()) })

    renderWithApp(App)

    expect(await screen.findByRole('heading', { name: 'Mirror your first channel' })).toBeTruthy()
    expect(screen.queryByText('Getting yt-mirror ready')).toBeNull()
  })
})
