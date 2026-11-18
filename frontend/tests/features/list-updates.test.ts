import { waitFor } from '@testing-library/vue'
import { describe, expect, it, vi } from 'vitest'

import { openApp, part } from '../helpers/app'
import { channel, CHANNEL_ID, NOW, video } from '../helpers/catalogue'

/**
 * One event about one video redraws that video, not the whole list (D-073, review of
 * M5: 180 ms per event at 5,000 videos). The list is worked out again only when the
 * change can move the video in or out of the tab, the search or the order; rows that
 * did not change keep what was worked out for them.
 */

const counted = vi.hoisted(() => ({ lists: 0, rows: 0 }))

vi.mock('@/features/channel/shown', async (original) => {
  const real = await original<typeof import('@/features/channel/shown')>()
  return {
    ...real,
    shownVideos: (...args: Parameters<typeof real.shownVideos>) => {
      counted.lists += 1
      return real.shownVideos(...args)
    },
  }
})

vi.mock('@/format', async (original) => {
  const real = await original<typeof import('@/format')>()
  return {
    ...real,
    // Called once for every row that is worked out (every fixture video has a duration).
    formatDuration: (...args: Parameters<typeof real.formatDuration>) => {
      counted.rows += 1
      return real.formatDuration(...args)
    },
  }
})

const APPROXIMATE = {
  published_at: null,
  published_precision: 'year',
  published_around: NOW,
} as const
const VIDEOS = Array.from({ length: 50 }, (_, index) =>
  index === 6 ? video(7, APPROXIMATE) : video(index + 1),
)

async function openList() {
  const app = await openApp({ channels: [channel({ videos: VIDEOS.length })], videos: VIDEOS })
  await waitFor(() => part(`[data-video="${video(50).id}"]`))
  counted.lists = 0
  counted.rows = 0
  return app
}

describe('one event about one video', () => {
  it('R-FB-03, R-UI-07: a new state of its date redraws its row only', async () => {
    const app = await openList()

    app
      .stream()
      .videoUpdated(
        CHANNEL_ID,
        video(7, { ...APPROXIMATE, date: { state: 'updating', reason: null, retry_at: null } }),
      )

    await waitFor(() =>
      expect(part(`[data-video="${video(7).id}"] [data-date]`).dataset.date).toBe('updating'),
    )
    expect(counted.lists).toBe(0)
    expect(counted.rows).toBe(0)
  })

  it('R-FB-03, R-UI-04: a new status works out the list again, and one row only', async () => {
    const app = await openList()

    app.stream().videoUpdated(CHANNEL_ID, video(7, { status: 'queued' }))

    await waitFor(() => expect(part(`[data-video="${video(7).id}"]`).dataset.status).toBe('queued'))
    expect(counted.lists).toBe(1)
    expect(counted.rows).toBe(1)
  })
})
