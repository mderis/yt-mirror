import { fireEvent, screen, waitFor, within } from '@testing-library/vue'
import { describe, expect, it } from 'vitest'

import App from '@/App.vue'

import { fakeEventStream } from '../helpers/events'
import { allToolsReady, healthyApi, jsonResponse, tool } from '../helpers/fetch'
import { renderWithApp } from '../helpers/render'

function withTool(changed: ReturnType<typeof tool>): ReturnType<typeof healthyApi> {
  const answer = allToolsReady()
  answer.tools = answer.tools.map((known) => (known.name === changed.name ? changed : known))
  return healthyApi({
    'GET /api/tools': jsonResponse(answer),
    [`POST /api/tools/${changed.name}/install`]: jsonResponse(
      tool(changed.name, 'installing', { progress: 0 }),
    ),
  })
}

function banner(name: string): HTMLElement {
  const found = document.querySelector<HTMLElement>(`[data-banner="${name}"]`)
  if (!found) {
    throw new Error(`No banner for ${name}`)
  }
  return found
}

describe('the banner of a tool that is not in order', () => {
  it('R-IN-04: no tool problem, no banner', async () => {
    healthyApi()

    renderWithApp(App)

    await screen.findByText('yt-mirror is running.')
    expect(document.querySelector('[data-banner]')).toBeNull()
  })

  it('R-IN-04: a missing tool gets a banner with an "Install now" button, not a crash', async () => {
    withTool(tool('ffmpeg', 'missing'))

    renderWithApp(App)

    await screen.findByText('yt-mirror is running.')
    expect(banner('ffmpeg').textContent).toContain(
      'ffmpeg is missing. yt-mirror cannot mirror videos without it.',
    )
    expect(banner('ffmpeg').getAttribute('role')).toBe('status')
    expect(within(banner('ffmpeg')).getByRole('button', { name: 'Install now' })).toBeTruthy()
    expect(screen.queryByText('Getting yt-mirror ready')).toBeNull()
  })

  it('R-IN-04: a broken tool says that it no longer works', async () => {
    withTool(tool('deno', 'broken', { version: '2.9.8', source: 'deno' }))

    renderWithApp(App)

    await screen.findByText('yt-mirror is running.')
    expect(banner('deno').textContent).toContain('Deno no longer works.')
    expect(within(banner('deno')).getByRole('button', { name: 'Install now' })).toBeTruthy()
  })

  it('R-IN-04: "Install now" starts the installation and the banner shows its progress', async () => {
    const newestStream = fakeEventStream()
    const fetchMock = withTool(tool('ffmpeg', 'missing'))
    renderWithApp(App)
    await screen.findByText('yt-mirror is running.')

    await fireEvent.click(within(banner('ffmpeg')).getByRole('button', { name: 'Install now' }))
    await waitFor(() => expect(banner('ffmpeg').textContent).toContain('Installing ffmpeg'))
    newestStream().toolUpdated(tool('ffmpeg', 'installing', { progress: 0.3 }), false)

    await waitFor(() =>
      expect(within(banner('ffmpeg')).getByRole('progressbar').getAttribute('aria-valuenow')).toBe(
        '30',
      ),
    )
    expect(fetchMock.mock.calls.at(-1)?.[0]).toBe('/api/tools/ffmpeg/install')
    expect(within(banner('ffmpeg')).queryByRole('button')).toBeNull()
  })

  it('R-IN-04: once the tool is installed the banner is gone', async () => {
    const newestStream = fakeEventStream()
    withTool(tool('ffmpeg', 'missing'))
    renderWithApp(App)
    await screen.findByText('yt-mirror is running.')

    newestStream().toolUpdated(tool('ffmpeg', 'ok'), false)

    await waitFor(() => expect(document.querySelector('[data-banner]')).toBeNull())
  })

  it('R-IN-04, R-ER-02: a failed installation says why and offers "Try again"', async () => {
    const newestStream = fakeEventStream()
    const fetchMock = withTool(tool('deno', 'missing'))
    renderWithApp(App)
    await screen.findByText('yt-mirror is running.')

    newestStream().toolUpdated(tool('deno', 'failed', { error_code: 'DISK_FULL' }), false)

    await waitFor(() =>
      expect(banner('deno').textContent).toContain(
        'Deno could not be installed: the disk is full.',
      ),
    )
    expect(banner('deno').getAttribute('role')).toBe('alert')
    await fireEvent.click(within(banner('deno')).getByRole('button', { name: 'Try again' }))
    expect(fetchMock.mock.calls.at(-1)?.[0]).toBe('/api/tools/deno/install')
  })

  it('R-IN-04: a failure with a code that has no words of its own still reads well', async () => {
    withTool(tool('deno', 'failed', { error_code: 'NOT_FOUND' }))

    renderWithApp(App)

    await screen.findByText('yt-mirror is running.')
    expect(banner('deno').textContent).toContain(
      'Deno could not be installed: an unexpected problem.',
    )
  })

  it('R-IN-04: a tool that only the launcher can repair has no button', async () => {
    withTool(tool('ytdlp', 'missing'))

    renderWithApp(App)

    await screen.findByText('yt-mirror is running.')
    expect(banner('ytdlp').textContent).toContain(
      'yt-dlp is missing. Quit yt-mirror and open it again to repair it.',
    )
    expect(within(banner('ytdlp')).queryByRole('button')).toBeNull()
  })
})
