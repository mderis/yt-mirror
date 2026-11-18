import { fireEvent, screen, waitFor } from '@testing-library/vue'
import { describe, expect, it } from 'vitest'

import { openApp, part } from '../helpers/app'
import { channel, CHANNEL_ID, video } from '../helpers/catalogue'
import { jsonResponse } from '../helpers/fetch'

const OTHER_ID = 'UCotherotherotherother02'

async function openWith() {
  const app = await openApp({
    channels: [channel(), channel({ id: OTHER_ID, title: 'Other Channel' })],
    videos: [video(1), video(2, { status: 'synced', height: 1080 }), video(3)],
    answers: {
      'POST /api/videos/mirror': jsonResponse({ jobs: [] }, 202),
      'PUT /api/state/view': jsonResponse({}),
      [`GET /api/videos/${video(1).id}`]: jsonResponse({}),
      [`GET /api/channels/${OTHER_ID}/videos`]: jsonResponse({ videos: [] }),
    },
  })
  await waitFor(() => part('[data-video]'))
  return app
}

async function press(key: string, options: KeyboardEventInit = {}): Promise<void> {
  await fireEvent.keyDown(document.body, { key, ...options })
}

function current(): string | undefined {
  return document.querySelector<HTMLElement>('[data-current]')?.dataset.video
}

describe('the keyboard shortcuts', () => {
  it('R-UI-13: the arrow keys move the current video', async () => {
    await openWith()

    await press('ArrowDown')
    expect(current()).toBe(video(1).id)
    await press('ArrowDown')
    await press('ArrowDown')
    await press('ArrowUp')

    expect(current()).toBe(video(2).id)
  })

  it('R-UI-13, R-MI-07: Space selects the current video and Esc clears the selection', async () => {
    await openWith()

    await press('ArrowDown')
    await press(' ')
    expect(await screen.findByRole('region', { name: 'Selected videos' })).toBeTruthy()
    await press('Escape')

    expect(screen.queryByRole('region', { name: 'Selected videos' })).toBeNull()
  })

  it('R-UI-13, R-MI-01: M mirrors the current video', async () => {
    const app = await openWith()

    await press('ArrowDown')
    await press('m')

    await waitFor(() =>
      expect(app.lastBody('/api/videos/mirror')).toEqual({ ids: [video(1).id], first: false }),
    )
  })

  it('R-UI-13, R-UI-08: Enter opens the details of the current video', async () => {
    const app = await openWith()

    await press('ArrowDown')
    await press('Enter')

    await waitFor(() => expect(app.requests()).toContain(`GET /api/videos/${video(1).id}`))
  })

  it('R-UI-13, R-MI-07: Cmd+A selects every shown video', async () => {
    await openWith()

    await press('a', { metaKey: true })

    const bar = await screen.findByRole('region', { name: 'Selected videos' })
    expect(bar.textContent).toContain('3 selected')
  })

  it('R-UI-13, R-UI-03: G switches to the grid; "/" goes to the search', async () => {
    const app = await openWith()

    await press('g')
    await waitFor(() => expect(app.lastBody('/api/state/view')).toEqual({ view: 'grid' }))
    await press('/')

    expect(document.activeElement).toBe(screen.getByRole('searchbox', { name: 'Filter by title' }))
  })

  it('R-UI-13: a key typed into the search is text, not a command', async () => {
    const app = await openWith()
    const search = screen.getByRole('searchbox', { name: 'Filter by title' })

    await fireEvent.keyDown(search, { key: 'g' })

    expect(app.requests()).not.toContain('PUT /api/state/view')
  })

  it('R-UI-13: a digit opens that channel of the sidebar', async () => {
    const app = await openWith()

    await press('2')

    await waitFor(() => expect(app.router.currentRoute.value.params.id).toBe(OTHER_ID))
  })

  it('R-UI-13, R-NA-09: "?" opens the list, which names Cmd+R for "Check channel now"', async () => {
    await openWith()

    await press('?')

    const dialog = await screen.findByRole('dialog', { name: 'Keyboard shortcuts' })
    expect(dialog.textContent).toContain('Check channel now')
    expect(dialog.textContent).toContain('⌘R')
  })

  it('R-UI-13, R-CH-23: Cmd+R checks the channel now', async () => {
    const app = await openApp({
      channels: [channel()],
      videos: [video(1)],
      answers: { [`POST /api/channels/${CHANNEL_ID}/check`]: jsonResponse(channel()) },
    })
    await waitFor(() => part('[data-video]'))

    await press('r', { metaKey: true })

    await waitFor(() => expect(app.requests()).toContain(`POST /api/channels/${CHANNEL_ID}/check`))
  })
})
