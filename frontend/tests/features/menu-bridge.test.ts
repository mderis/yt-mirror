import { fireEvent, screen, waitFor, within } from '@testing-library/vue'
import { describe, expect, it } from 'vitest'

import type { Queue } from '@/api/client'

import { noContent, openApp, part } from '../helpers/app'
import { channel, CHANNEL_ID, video } from '../helpers/catalogue'
import { jsonResponse } from '../helpers/fetch'

function queue(changes: Partial<Queue> = {}): Queue {
  return {
    downloading: 2,
    waiting: 4,
    failed: 0,
    paused: false,
    places: 2,
    speed_limit_mbps: 0,
    folders_away: [],
    ...changes,
  }
}

describe('the menu bar bridge', () => {
  it('R-NA-04, D-094: the shell reports what applies, and reports again when it changes', async () => {
    const app = await openApp({
      channels: [channel({ videos: 3, synced: 1 })],
      videos: [video(1)],
      answers: { 'PUT /api/state/view': jsonResponse({}) },
    })

    await waitFor(() =>
      expect(app.lastBody('/api/ui/state')).toEqual({
        channel_open: true,
        paused: false,
        checking: false,
        has_missing: true,
        folder_available: true,
        view: 'list',
        any_unpaused: true,
      }),
    )
    app.stream().channelUpdated(channel({ videos: 3, synced: 1, paused: true, status: 'paused' }))

    await waitFor(() =>
      expect(app.lastBody('/api/ui/state')).toMatchObject({ paused: true, any_unpaused: false }),
    )
  })

  it('R-NA-03, D-094: a command of the menu bar runs what its control runs', async () => {
    const app = await openApp({
      channels: [channel({ videos: 3, synced: 1 })],
      videos: [video(1)],
      answers: {
        [`POST /api/channels/${CHANNEL_ID}/check`]: jsonResponse(channel()),
        [`POST /api/channels/${CHANNEL_ID}/mirror-missing`]: jsonResponse({ jobs: [] }, 202),
      },
    })
    await waitFor(() => part('[data-video]'))

    app.stream().menuCommand('check_now')
    app.stream().menuCommand('mirror_missing')
    app.stream().menuCommand('add_channel')

    await waitFor(() => expect(app.requests()).toContain(`POST /api/channels/${CHANNEL_ID}/check`))
    await waitFor(() =>
      expect(app.requests()).toContain(`POST /api/channels/${CHANNEL_ID}/mirror-missing`),
    )
    expect(await screen.findByRole('dialog', { name: 'Add a channel' })).toBeTruthy()
  })

  it('R-NA-04, R-CH-31: "Check Now" from the menu does nothing for a paused channel', async () => {
    const app = await openApp({
      channels: [channel({ paused: true, status: 'paused' })],
      videos: [video(1)],
    })
    await waitFor(() => part('[data-video]'))

    app.stream().menuCommand('check_now')
    await new Promise((resolve) => setTimeout(resolve, 20))

    expect(app.requests()).not.toContain(`POST /api/channels/${CHANNEL_ID}/check`)
  })

  it('R-UI-13, R-NA-09: Keyboard Shortcuts in the Help menu opens the list', async () => {
    const app = await openApp({ channels: [channel()], videos: [video(1)] })

    app.stream().menuCommand('shortcuts')

    expect(await screen.findByRole('dialog', { name: 'Keyboard shortcuts' })).toBeTruthy()
  })
})

describe('the quit question', () => {
  it('R-QU-12, R-NA-06: a held quit asks, with how many run and wait; "Quit" confirms', async () => {
    const app = await openApp({
      channels: [channel()],
      videos: [video(1)],
      state: { queue: queue() },
      answers: { 'POST /api/ui/quit': noContent() },
    })

    app.stream().quitAsked()

    const dialog = await screen.findByRole('dialog', { name: 'Quit yt-mirror?' })
    expect(dialog.textContent).toContain('2 videos are downloading and 4 are waiting.')
    expect(dialog.textContent).toContain('Downloads stop. Nothing is lost.')
    expect(dialog.textContent).not.toContain('Do not ask again')
    await fireEvent.click(within(dialog).getByRole('button', { name: 'Quit' }))

    await waitFor(() => expect(app.requests()).toContain('POST /api/ui/quit'))
  })

  it('R-QU-12: "Keep running" closes the question and changes nothing', async () => {
    const app = await openApp({
      channels: [channel()],
      videos: [video(1)],
      state: { queue: queue() },
    })

    app.stream().quitAsked()
    const dialog = await screen.findByRole('dialog', { name: 'Quit yt-mirror?' })
    const [, keep] = within(dialog).getAllByRole('button', { name: 'Keep running' })
    await fireEvent.click(keep as HTMLElement)

    expect(screen.queryByRole('dialog', { name: 'Quit yt-mirror?' })).toBeNull()
    expect(app.requests()).not.toContain('POST /api/ui/quit')
  })
})
