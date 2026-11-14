import { fireEvent, screen } from '@testing-library/vue'
import { describe, expect, it } from 'vitest'

import { openApp, part } from '../helpers/app'
import { CHANNEL_ID } from '../helpers/catalogue'
import { jsonResponse } from '../helpers/fetch'

const preview = {
  channel_id: CHANNEL_ID,
  title: 'Sample Channel',
  handle: '@sample',
  has_avatar: true,
  existing: false,
  folder: '/Users/sam/Movies/YouTube/Sample Channel',
  video_files: 0,
}

describe('the welcome screen', () => {
  it('R-UI-02: says what to do first, and where videos will be saved', async () => {
    await openApp()

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Mirror your first channel' }),
    ).toBeTruthy()
    expect(screen.getByText(/Paste a YouTube channel link or @handle/)).toBeTruthy()
    expect(screen.getByRole('textbox', { name: 'Channel link or handle' })).toBeTruthy()
    expect(part('[data-library]').textContent?.trim()).toBe(
      'Videos will be saved in /Users/sam/Movies/YouTube.',
    )
  })

  it('R-CH-01: what is pasted on the welcome screen is looked up in the add channel dialog', async () => {
    const app = await openApp({
      answers: {
        'POST /api/channels/lookup': jsonResponse(preview),
        [`GET /api/channels/lookup/${CHANNEL_ID}/video-count`]: jsonResponse({ video_count: null }),
      },
    })
    const field = await screen.findByRole('textbox', { name: 'Channel link or handle' })

    await fireEvent.update(field, ' @sample ')
    await fireEvent.click(screen.getByRole('main').querySelector('button') as HTMLElement)

    expect(await screen.findByRole('dialog', { name: 'Add a channel' })).toBeTruthy()
    expect(await screen.findByText('Found')).toBeTruthy()
    expect(app.lastBody('/api/channels/lookup')).toEqual({ text: '@sample' })
  })

  it('R-CH-01: Enter in the field of the welcome screen does the same as the button', async () => {
    await openApp()
    const field = await screen.findByRole('textbox', { name: 'Channel link or handle' })

    await fireEvent.keyDown(field, { key: 'Enter' })

    expect(await screen.findByRole('dialog', { name: 'Add a channel' })).toBeTruthy()
    expect(screen.queryByText('Looking up the channel...')).toBeNull()
  })
})
