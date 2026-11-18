import { fireEvent, screen, waitFor, within } from '@testing-library/vue'
import { describe, expect, it } from 'vitest'

import type { Queue, QueueAnswer, QueueItem } from '@/api/client'

import { noContent, openApp } from '../helpers/app'
import { channel, CHANNEL_ID, NOW, video } from '../helpers/catalogue'
import { jsonResponse } from '../helpers/fetch'

function summary(changes: Partial<Queue> = {}): Queue {
  return {
    downloading: 1,
    waiting: 2,
    failed: 1,
    paused: false,
    places: 2,
    speed_limit_mbps: 0,
    folders_away: [],
    ...changes,
  }
}

function item(number: number, changes: Partial<QueueItem> = {}): QueueItem {
  return {
    job_id: `J${number}`,
    video_id: video(number).id,
    channel_id: CHANNEL_ID,
    channel_title: 'Sample Channel',
    title: `Video ${number}`,
    duration_s: 600,
    quality: '1080',
    by_hand: true,
    download: null,
    paced_until: null,
    ...changes,
  }
}

const FULL: QueueAnswer = {
  queue: summary(),
  running: [item(1)],
  waiting: [item(2), item(3, { by_hand: false, paced_until: NOW + 600 })],
  failed: [
    {
      video_id: video(4).id,
      channel_id: CHANNEL_ID,
      channel_title: 'Sample Channel',
      title: 'Video 4',
      error_code: 'MEMBERS_ONLY',
      attempts: 0,
      gone: false,
    },
  ],
}

async function openWithQueue(queue: Queue = summary(), answers = {}) {
  return openApp({
    channels: [channel()],
    videos: [video(1)],
    state: { queue },
    answers: {
      'GET /api/queue': jsonResponse(FULL),
      'POST /api/queue/pause': jsonResponse(summary({ paused: true })),
      'POST /api/queue/reorder': noContent(),
      'POST /api/queue/clear-waiting': jsonResponse({ removed: 2 }),
      'POST /api/queue/speed-limit': jsonResponse(summary({ speed_limit_mbps: 2 })),
      ...answers,
    },
  })
}

async function openPanel(): Promise<HTMLElement> {
  const bar = await screen.findByRole('region', { name: 'Downloads' })
  await fireEvent.click(within(bar).getByRole('button', { name: 'Show queue' }))
  const panel = await screen.findByRole('complementary', { name: 'Downloads' })
  // The whole queue arrives after the panel opened.
  await waitFor(() => expect(panel.querySelector('[data-job]')).not.toBeNull())
  return panel
}

describe('the queue bar', () => {
  it('R-QU-02: says how many run, wait and failed, and pauses all', async () => {
    const app = await openWithQueue()

    const bar = await screen.findByRole('region', { name: 'Downloads' })
    expect(bar.textContent).toContain('1 downloading')
    expect(bar.textContent).toContain('2 waiting')
    await fireEvent.click(within(bar).getByRole('button', { name: 'Pause all' }))

    await waitFor(() => expect(app.requests()).toContain('POST /api/queue/pause'))
    await waitFor(() => expect(bar.textContent).toContain('All downloads paused'))
  })

  it('R-FB-03, R-QU-02: follows the queue as the events tell it', async () => {
    const app = await openWithQueue(summary({ downloading: 0, waiting: 0, failed: 0 }))
    expect(screen.queryByRole('region', { name: 'Downloads' })).toBeNull()

    app.stream().queueUpdated(summary({ downloading: 2, waiting: 0, failed: 0 }))

    const bar = await screen.findByRole('region', { name: 'Downloads' })
    expect(bar.textContent).toContain('2 downloading')
  })
})

describe('the downloads panel', () => {
  it('R-QU-02, R-QU-08, D-090: lists what runs, waits and failed, with a paced one', async () => {
    await openWithQueue()

    const panel = await openPanel()

    expect(within(panel).getByText('Downloading now (2 at a time)')).toBeTruthy()
    expect(panel.querySelector('[data-job="J1"]')?.textContent).toContain('Video 1')
    expect(panel.querySelector('[data-job="J3"]')?.textContent).toContain(
      'Waiting · paced to protect your access to YouTube',
    )
    expect(panel.querySelector(`[data-failed-video="${video(4).id}"]`)?.textContent).toContain(
      'Members-only video',
    )
    expect(panel.textContent).toContain('Unfinished downloads continue')
  })

  it('R-QU-02, R-UI-13: Alt and an arrow key move a waiting download', async () => {
    const app = await openWithQueue()
    const panel = await openPanel()

    const second = panel.querySelector<HTMLElement>('[data-job="J3"]')
    expect(second).not.toBeNull()
    await fireEvent.keyDown(second as HTMLElement, { key: 'ArrowUp', altKey: true })

    await waitFor(() =>
      expect(app.lastBody('/api/queue/reorder')).toEqual({ job_ids: ['J3', 'J2'] }),
    )
  })

  it('R-QU-02: a dragged download is dropped in its new place', async () => {
    const app = await openWithQueue()
    const panel = await openPanel()
    const first = panel.querySelector<HTMLElement>('[data-job="J2"]') as HTMLElement
    const second = panel.querySelector<HTMLElement>('[data-job="J3"]') as HTMLElement

    await fireEvent.dragStart(second)
    await fireEvent.drop(first)

    await waitFor(() =>
      expect(app.lastBody('/api/queue/reorder')).toEqual({ job_ids: ['J3', 'J2'] }),
    )
  })

  it('R-QU-02, R-UI-12: "Clear waiting" asks first', async () => {
    const app = await openWithQueue()
    const panel = await openPanel()

    await fireEvent.click(within(panel).getByRole('button', { name: 'Clear waiting' }))
    const dialog = await screen.findByRole('dialog', { name: 'Clear the waiting downloads?' })
    expect(app.requests()).not.toContain('POST /api/queue/clear-waiting')
    await fireEvent.click(within(dialog).getByRole('button', { name: 'Clear waiting' }))

    await waitFor(() => expect(app.requests()).toContain('POST /api/queue/clear-waiting'))
  })

  it('R-QU-03: the speed limit is chosen in the panel', async () => {
    const app = await openWithQueue()
    const panel = await openPanel()

    await fireEvent.update(within(panel).getByRole('combobox', { name: 'Speed limit' }), '2')

    await waitFor(() => expect(app.lastBody('/api/queue/speed-limit')).toEqual({ mbps: 2 }))
  })
})

describe('the banners of the queue', () => {
  it('R-QU-10: the disk space guard says why the queue waits, and resumes anyway', async () => {
    const app = await openWithQueue(
      summary({
        disk_guard: { disk: 'Media', free_bytes: 9_000_000_000, limit_bytes: 10_000_000_000 },
      }),
      { 'POST /api/queue/resume-anyway': jsonResponse(summary()) },
    )

    const banner = await screen.findByText(/Queue paused: only/)
    expect(banner.textContent).toContain('Media')
    await fireEvent.click(screen.getByRole('button', { name: 'Resume anyway' }))

    await waitFor(() => expect(app.requests()).toContain('POST /api/queue/resume-anyway'))
  })

  it('R-QU-11: a channel folder that cannot be reached holds its downloads, with Try again', async () => {
    const app = await openWithQueue(summary({ folders_away: [CHANNEL_ID] }), {
      [`POST /api/queue/folders/${CHANNEL_ID}/try-again`]: jsonResponse({ available: true }),
    })

    expect(
      await screen.findByText(
        'The folder of Sample Channel cannot be reached. Its downloads wait.',
      ),
    ).toBeTruthy()
    await fireEvent.click(screen.getByRole('button', { name: 'Try again' }))

    await waitFor(() =>
      expect(app.requests()).toContain(`POST /api/queue/folders/${CHANNEL_ID}/try-again`),
    )
  })
})
