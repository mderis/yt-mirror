import { fireEvent, screen, waitFor, within } from '@testing-library/vue'
import { describe, expect, it } from 'vitest'

import { channel, CHANNEL_ID, NOW, OTHER_CHANNEL_ID } from '../helpers/catalogue'
import { noContent, openApp, part } from '../helpers/app'
import { allToolsReady, errorBody, jsonResponse, tool } from '../helpers/fetch'

const other = channel({ id: OTHER_CHANNEL_ID, title: 'Other Channel', pictures: 0 })

function sidebar(): HTMLElement {
  return screen.getByRole('navigation', { name: 'Channels' })
}

function item(title: string): HTMLElement {
  return within(sidebar()).getByRole('button', { name: new RegExp(title) })
}

describe('the shell', () => {
  it('R-UI-01: one shell with the channels, "Add channel", the free disk space and a main area', async () => {
    await openApp({ channels: [channel(), other] })

    expect(within(sidebar()).getByText('yt-mirror')).toBeTruthy()
    expect(item('Sample Channel')).toBeTruthy()
    expect(item('Other Channel')).toBeTruthy()
    expect(within(sidebar()).getByRole('button', { name: 'Add channel' })).toBeTruthy()
    expect(part('[data-free-space]').textContent).toBe('412 GB free on Macintosh HD')
    expect(await screen.findByRole('main')).toBeTruthy()
  })

  it('R-UI-02: with no channels the app shows the welcome screen', async () => {
    await openApp()

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Mirror your first channel' }),
    ).toBeTruthy()
  })

  it('R-UI-02: the app opens on the channel that was open last', async () => {
    await openApp({
      channels: [channel(), other],
      state: { open_channel_id: OTHER_CHANNEL_ID },
      answers: { [`GET /api/channels/${OTHER_CHANNEL_ID}/videos`]: jsonResponse({ videos: [] }) },
    })

    expect(await screen.findByRole('heading', { level: 1, name: 'Other Channel' })).toBeTruthy()
    expect(item('Other Channel').getAttribute('aria-current')).toBe('page')
  })

  it('R-CH-34: the sidebar shows per channel the avatar, the name, one status line and the new count', async () => {
    await openApp({
      channels: [channel({ status: 'new_videos', new_videos: 3, avatar_version: 4 }), other],
    })

    const first = item('Sample Channel')
    expect(first.querySelector('img')?.getAttribute('src')).toBe(
      `/api/channels/${CHANNEL_ID}/avatar?v=4`,
    )
    expect(first.querySelector('[data-status]')?.textContent).toBe('3 new videos')
    expect(within(first).getByText('3 new')).toBeTruthy()
    expect(item('Other Channel').textContent).not.toContain('new')
  })

  it('R-FB-01: every status of a channel has words and an icon of its own', async () => {
    const statuses = [
      channel({ id: 'UC1', title: 'One', status: 'checking' }),
      channel({ id: 'UC2', title: 'Two', status: 'up_to_date', last_check_at: NOW - 125 }),
      channel({ id: 'UC3', title: 'Three', status: 'new_videos', new_videos: 1 }),
      channel({ id: 'UC4', title: 'Four', status: 'paused', paused: true }),
      channel({ id: 'UC5', title: 'Five', status: 'could_not_check' }),
    ]
    await openApp({ channels: statuses })

    const lines = [...sidebar().querySelectorAll('[data-status]')]
    expect(lines.map((line) => line.textContent)).toEqual([
      'Checking for new videos...',
      'Up to date · checked 2 min ago',
      '1 new video',
      'Paused',
      'Could not check',
    ])
    expect(lines.every((line) => line.querySelector('svg') !== null)).toBe(true)
  })

  it('R-CH-11: a channel that was never listed says in the sidebar that it is being read', async () => {
    await openApp({
      channels: [channel({ status: 'up_to_date', first_listed_at: null, last_check_at: null })],
    })

    expect(sidebar().querySelector('[data-status]')?.textContent).toBe('Checking for new videos...')
  })

  it('R-UI-01: a click on a channel opens its page and marks it in the sidebar', async () => {
    await openApp({
      channels: [channel(), other],
      answers: { [`GET /api/channels/${OTHER_CHANNEL_ID}/videos`]: jsonResponse({ videos: [] }) },
    })
    await screen.findByRole('heading', { level: 1, name: 'Sample Channel' })

    await fireEvent.click(item('Other Channel'))

    expect(await screen.findByRole('heading', { level: 1, name: 'Other Channel' })).toBeTruthy()
    expect(item('Other Channel').getAttribute('aria-current')).toBe('page')
    expect(item('Sample Channel').getAttribute('aria-current')).toBeNull()
  })

  it('R-UI-02: opening a channel tells the backend which one is open', async () => {
    const app = await openApp({
      channels: [channel(), other],
      answers: { [`GET /api/channels/${OTHER_CHANNEL_ID}/videos`]: jsonResponse({ videos: [] }) },
    })
    await screen.findByRole('heading', { level: 1, name: 'Sample Channel' })

    await fireEvent.click(item('Other Channel'))
    await screen.findByRole('heading', { level: 1, name: 'Other Channel' })

    expect(app.lastBody('/api/state/open-channel')).toEqual({ channel_id: OTHER_CHANNEL_ID })
  })

  it('R-CH-23: "Check all channels now" asks for a check of every channel and is busy meanwhile', async () => {
    let answer: (response: Response) => void = () => {}
    const app = await openApp({
      channels: [channel()],
      answers: {
        'POST /api/channels/check-all': () =>
          new Promise<Response>((resolve) => (answer = resolve)),
      },
    })
    const button = within(sidebar()).getByRole('button', { name: 'Check all channels now' })

    await fireEvent.click(button)
    const busy = button.getAttribute('aria-busy')
    answer(jsonResponse({ channels: 1 }))

    expect(busy).toBe('true')
    await waitFor(() => expect(button.getAttribute('aria-busy')).not.toBe('true'))
    expect(app.requests()).toContain('POST /api/channels/check-all')
  })

  it('R-FB-03: a channel event of the stream changes the status line without a reload', async () => {
    const app = await openApp({ channels: [channel()] })

    app.stream().channelUpdated(channel({ status: 'checking' }))

    await waitFor(() =>
      expect(sidebar().querySelector('[data-status]')?.textContent).toBe(
        'Checking for new videos...',
      ),
    )
  })

  it('R-CH-30: a right-click on a channel offers what can be done with it', async () => {
    await openApp({ channels: [channel()] })

    await fireEvent.contextMenu(item('Sample Channel'))

    const menu = await screen.findByRole('menu', { name: 'Actions of Sample Channel' })
    expect(
      within(menu)
        .getAllByRole('menuitem')
        .map((entry) => entry.textContent?.trim()),
    ).toEqual([
      'Check now',
      'Full check',
      'Pause channel',
      'Open folder',
      'Open on YouTube',
      'Remove channel',
    ])
    expect(
      within(menu).getByRole('menuitem', { name: 'Open on YouTube' }).getAttribute('href'),
    ).toBe(`https://www.youtube.com/channel/${CHANNEL_ID}`)
  })

  it('R-CH-31: a paused channel is offered "Resume channel" and no check', async () => {
    await openApp({ channels: [channel({ paused: true, status: 'paused' })] })

    await fireEvent.contextMenu(item('Sample Channel'))

    const menu = await screen.findByRole('menu')
    expect(
      within(menu)
        .getAllByRole('menuitem')
        .map((entry) => entry.textContent?.trim()),
    ).toEqual(['Resume channel', 'Open folder', 'Open on YouTube', 'Remove channel'])
  })

  it('R-CH-23: "Check now" and "Full check" of the menu start a check of that kind', async () => {
    const app = await openApp({
      channels: [channel()],
      answers: {
        [`POST /api/channels/${CHANNEL_ID}/check`]: jsonResponse(channel({ status: 'checking' })),
      },
    })

    await fireEvent.contextMenu(item('Sample Channel'))
    await fireEvent.click(await screen.findByRole('menuitem', { name: 'Full check' }))
    await waitFor(() => expect(screen.queryByRole('menu')).toBeNull())
    const full = app.lastBody(`/api/channels/${CHANNEL_ID}/check`)
    await fireEvent.contextMenu(item('Sample Channel'))
    await fireEvent.click(await screen.findByRole('menuitem', { name: 'Check now' }))

    expect(full).toEqual({ kind: 'full' })
    await waitFor(() =>
      expect(app.lastBody(`/api/channels/${CHANNEL_ID}/check`)).toEqual({ kind: 'quick' }),
    )
  })

  it('R-CH-31: the menu pauses a channel and resumes it', async () => {
    const answers = [
      jsonResponse(channel({ paused: true, status: 'paused' })),
      jsonResponse(channel()),
    ]
    const app = await openApp({
      channels: [channel()],
      answers: { [`PATCH /api/channels/${CHANNEL_ID}`]: () => answers.shift() as Response },
    })

    await fireEvent.contextMenu(item('Sample Channel'))
    await fireEvent.click(await screen.findByRole('menuitem', { name: 'Pause channel' }))
    await waitFor(() =>
      expect(sidebar().querySelector('[data-status]')?.textContent).toBe('Paused'),
    )
    const paused = app.lastBody(`/api/channels/${CHANNEL_ID}`)
    await fireEvent.contextMenu(item('Sample Channel'))
    await fireEvent.click(await screen.findByRole('menuitem', { name: 'Resume channel' }))

    expect(paused).toEqual({ paused: true })
    await waitFor(() =>
      expect(app.lastBody(`/api/channels/${CHANNEL_ID}`)).toEqual({ paused: false }),
    )
  })

  it('R-CH-30: "Open folder" of the menu asks to show the folder of the channel', async () => {
    const app = await openApp({
      channels: [channel()],
      answers: { [`POST /api/channels/${CHANNEL_ID}/open-folder`]: noContent() },
    })

    await fireEvent.contextMenu(item('Sample Channel'))
    await fireEvent.click(await screen.findByRole('menuitem', { name: 'Open folder' }))

    await waitFor(() =>
      expect(app.requests()).toContain(`POST /api/channels/${CHANNEL_ID}/open-folder`),
    )
  })

  it('R-ER-01, R-ER-02: an action that fails says what happened and what to do, until it is dismissed', async () => {
    await openApp({
      channels: [channel()],
      answers: {
        [`POST /api/channels/${CHANNEL_ID}/open-folder`]: jsonResponse(
          errorBody('FOLDER_UNAVAILABLE'),
          409,
        ),
      },
    })

    await fireEvent.contextMenu(item('Sample Channel'))
    await fireEvent.click(await screen.findByRole('menuitem', { name: 'Open folder' }))

    const banner = await waitFor(() => part('[data-banner="action-failed"]'))
    expect(banner.textContent).toContain('The folder cannot be used.')
    expect(banner.textContent).toContain('choose another folder')
    await fireEvent.click(within(banner).getByRole('button', { name: 'Dismiss' }))
    expect(document.querySelector('[data-banner="action-failed"]')).toBeNull()
  })

  it('R-IN-04: a tool that is missing after the first run shows its banner above the page', async () => {
    const tools = allToolsReady()
    tools.tools[2] = tool('ffmpeg', 'missing')
    await openApp({ channels: [channel()], answers: { 'GET /api/tools': jsonResponse(tools) } })

    expect(part('[data-banners] [data-banner="ffmpeg"]').textContent).toContain('ffmpeg is missing')
  })
})
