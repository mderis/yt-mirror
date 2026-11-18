import { fireEvent, screen, waitFor, within } from '@testing-library/vue'
import { describe, expect, it } from 'vitest'

import type { Download, VideoDetails } from '@/api/client'

import { noContent, openApp, part } from '../helpers/app'
import { channel, CHANNEL_ID, NOW, video } from '../helpers/catalogue'
import { errorBody, jsonResponse } from '../helpers/fetch'

const ID = video(1).id

function row(): HTMLElement {
  return part(`[data-video="${ID}"]`)
}

/** Open the app on the sample channel with one video, as given. */
async function openWith(changes: Parameters<typeof video>[1] = {}, answers = {}) {
  const app = await openApp({
    channels: [channel()],
    videos: [video(1, changes)],
    answers: {
      'POST /api/videos/mirror': jsonResponse({ jobs: [{ job_id: 'J1', video_id: ID }] }, 202),
      ...answers,
    },
  })
  await waitFor(() => row())
  return app
}

function download(changes: Partial<Download> = {}): Download {
  return {
    job_id: 'J1',
    video_id: ID,
    channel_id: CHANNEL_ID,
    stage: 'video',
    fraction: 0.42,
    speed_bps: 3_100_000,
    left_s: 65,
    height: 1080,
    downloaded_bytes: 1_200_000_000,
    total_bytes: 2_860_000_000,
    parts: [],
    again: false,
    ...changes,
  }
}

describe('downloading videos', () => {
  it('R-MI-01: "Mirror" on a row puts that video in line', async () => {
    const app = await openWith()

    await fireEvent.click(within(row()).getByRole('button', { name: 'Mirror' }))

    await waitFor(() =>
      expect(app.lastBody('/api/videos/mirror')).toEqual({ ids: [ID], first: false }),
    )
  })

  it('R-FB-02, R-FB-03, R-QU-02: a queued video says so at once and can be cancelled', async () => {
    const app = await openWith(
      {},
      { 'POST /api/jobs/J1/cancel': jsonResponse({ cancelled: true }) },
    )

    app.stream().videoUpdated(CHANNEL_ID, video(1, { status: 'queued', job_id: 'J1' }))

    await waitFor(() => expect(within(row()).getByText('Queued')).toBeTruthy())
    await fireEvent.click(
      within(row()).getByRole('button', { name: 'Cancel the download of Video 1' }),
    )
    await waitFor(() => expect(app.requests()).toContain('POST /api/jobs/J1/cancel'))
  })

  it('R-QU-04: a download reads "Downloading 62% · 340 of 550 MB · about 2 min left"', async () => {
    const app = await openWith()

    app.stream().videoUpdated(CHANNEL_ID, video(1, { status: 'downloading', job_id: 'J1' }))
    app.stream().jobProgress(download())

    await waitFor(() => expect(within(row()).getByText('Downloading 42%')).toBeTruthy())
    expect(part('[data-progress-facts]').textContent).toBe('1.2 of 2.9 GB · about 2 min left')
    const bar = within(row()).getByRole('progressbar', { name: 'Progress of Video 1' })
    expect(bar.getAttribute('aria-valuenow')).toBe('42')
    expect(
      within(row()).getByRole('button', { name: 'Cancel the download of Video 1' }),
    ).toBeTruthy()
  })

  it('R-QU-04: the percent and the bar grow as the whole video arrives', async () => {
    const app = await openWith()
    app.stream().videoUpdated(CHANNEL_ID, video(1, { status: 'downloading', job_id: 'J1' }))
    const bar = () => within(row()).getByRole('progressbar', { name: 'Progress of Video 1' })

    for (const [fraction, percent] of [
      [0.1, '10'],
      [0.55, '55'],
      [0.9, '90'],
    ] as const) {
      app.stream().jobProgress(download({ fraction, stage: fraction < 0.75 ? 'video' : 'audio' }))
      await waitFor(() => expect(within(row()).getByText(`Downloading ${percent}%`)).toBeTruthy())
      expect(bar().getAttribute('aria-valuenow')).toBe(percent)
      expect((bar().firstElementChild as HTMLElement).style.width).toBe(`${percent}%`)
    }
  })

  it('R-QU-04: without a size the row says how much arrived, and makes up no percent', async () => {
    const app = await openWith()

    app.stream().videoUpdated(CHANNEL_ID, video(1, { status: 'downloading', job_id: 'J1' }))
    app.stream().jobProgress(download({ fraction: null, downloaded_bytes: 120_000_000 }))

    await waitFor(() => expect(within(row()).getByText('Downloading · 120 MB')).toBeTruthy())
    const bar = within(row()).getByRole('progressbar', { name: 'Progress of Video 1' })
    expect(bar.hasAttribute('aria-valuenow')).toBe(false)
    expect(bar.querySelector('[data-working]')).not.toBeNull()
  })

  it('R-QU-04: while the video is processed the bar shows that the step runs, with no percent', async () => {
    const app = await openWith()

    app.stream().videoUpdated(CHANNEL_ID, video(1, { status: 'processing', job_id: 'J1' }))
    app.stream().jobProgress(download({ stage: 'processing', fraction: null }))

    await waitFor(() => expect(within(row()).getByText('Processing')).toBeTruthy())
    const bar = within(row()).getByRole('progressbar', { name: 'Progress of Video 1' })
    expect(bar.hasAttribute('aria-valuenow')).toBe(false)
    expect(bar.querySelector('[data-working]')).not.toBeNull()
    expect(row().textContent).not.toMatch(/\d+%/)
  })

  it('R-QU-04: a download that runs when the list is loaded shows its progress at once', async () => {
    await openWith({ status: 'downloading', job_id: 'J1', download: download() })

    expect(within(row()).getByText('Downloading 42%')).toBeTruthy()
  })

  it('R-QU-02: a video that is processed can still be cancelled', async () => {
    const app = await openWith()

    app.stream().videoUpdated(CHANNEL_ID, video(1, { status: 'processing', job_id: 'J1' }))

    await waitFor(() => expect(within(row()).getByText('Processing')).toBeTruthy())
    expect(
      within(row()).getByRole('button', { name: 'Cancel the download of Video 1' }),
    ).toBeTruthy()
  })

  it('R-QU-02: after Cancel a download that writes says "Cancelling…", busy, until it ends', async () => {
    const app = await openWith(
      {},
      { 'POST /api/jobs/J1/cancel': jsonResponse({ cancelled: true }) },
    )
    app.stream().videoUpdated(CHANNEL_ID, video(1, { status: 'downloading', job_id: 'J1' }))
    app.stream().jobProgress(download())
    await waitFor(() => expect(within(row()).getByText('Downloading 42%')).toBeTruthy())

    await fireEvent.click(
      within(row()).getByRole('button', { name: 'Cancel the download of Video 1' }),
    )

    await waitFor(() => expect(within(row()).getByText('Cancelling…')).toBeTruthy())
    expect(within(row()).queryByText('Downloading 42%')).toBeNull()
    expect(within(row()).queryByRole('progressbar')).toBeNull()
    const button = within(row()).getByRole('button', { name: 'Cancel the download of Video 1' })
    expect(button.getAttribute('aria-busy')).toBe('true')

    app.stream().videoUpdated(CHANNEL_ID, video(1, { status: 'not_downloaded' }))

    await waitFor(() => expect(within(row()).getByText('Not downloaded')).toBeTruthy())
    expect(within(row()).queryByText('Cancelling…')).toBeNull()
    expect(within(row()).getByRole('button', { name: 'Mirror' })).toBeTruthy()
  })

  it('R-QU-02: a cancel the server refuses shows the download again', async () => {
    const app = await openWith(
      {},
      { 'POST /api/jobs/J1/cancel': jsonResponse(errorBody('INTERNAL'), 500) },
    )
    app.stream().videoUpdated(CHANNEL_ID, video(1, { status: 'downloading', job_id: 'J1' }))
    app.stream().jobProgress(download())
    await waitFor(() => expect(within(row()).getByText('Downloading 42%')).toBeTruthy())

    await fireEvent.click(
      within(row()).getByRole('button', { name: 'Cancel the download of Video 1' }),
    )

    await waitFor(() => expect(within(row()).getByText('Downloading 42%')).toBeTruthy())
    expect(within(row()).queryByText('Cancelling…')).toBeNull()
  })

  it('R-FB-02, R-UI-10: a synced video shows its height and size, and plays and shows in Finder', async () => {
    const app = await openWith(
      {},
      {
        [`POST /api/videos/${ID}/play`]: noContent(),
        [`POST /api/videos/${ID}/reveal`]: noContent(),
      },
    )

    app
      .stream()
      .videoUpdated(
        CHANNEL_ID,
        video(1, { status: 'synced', height: 1080, file_size: 412_000_000 }),
      )

    await waitFor(() => expect(within(row()).getByText('Synced · 1080p')).toBeTruthy())
    expect(part('[data-size]').textContent).toBe('412 MB')
    await fireEvent.click(within(row()).getByRole('button', { name: 'Play' }))
    await fireEvent.click(within(row()).getByRole('button', { name: 'Show in Finder' }))
    await waitFor(() =>
      expect(app.requests()).toEqual(
        expect.arrayContaining([`POST /api/videos/${ID}/play`, `POST /api/videos/${ID}/reveal`]),
      ),
    )
  })

  it.each(['not_downloaded', 'file_missing'] as const)(
    'R-CH-14: a video removed from YouTube offers no Mirror (%s)',
    async (status) => {
      await openWith({ status, gone: true })

      expect(within(row()).getByText('Removed from YouTube')).toBeTruthy()
      expect(within(row()).queryByRole('button', { name: 'Mirror' })).toBeNull()
    },
  )

  it('R-CH-14, R-UI-10: a synced video removed from YouTube still plays and shows in Finder', async () => {
    await openWith({ status: 'synced', gone: true, height: 1080, file_size: 412_000_000 })

    expect(within(row()).getByText('Removed from YouTube')).toBeTruthy()
    expect(within(row()).getByRole('button', { name: 'Play' })).toBeTruthy()
    expect(within(row()).getByRole('button', { name: 'Show in Finder' })).toBeTruthy()
    expect(within(row()).queryByRole('button', { name: 'Mirror' })).toBeNull()
  })

  it('R-QU-08, R-ER-03: a failed video says why and offers Retry', async () => {
    const app = await openWith(
      {},
      { [`POST /api/videos/${ID}/retry`]: jsonResponse(video(1, { status: 'queued' }), 202) },
    )

    app
      .stream()
      .videoUpdated(CHANNEL_ID, video(1, { status: 'failed', error_code: 'MEMBERS_ONLY' }))

    await waitFor(() => expect(within(row()).getByText('Failed')).toBeTruthy())
    expect(part('[data-reason]').textContent).toBe('Members-only video')
    await fireEvent.click(within(row()).getByRole('button', { name: 'Retry' }))
    await waitFor(() => expect(app.requests()).toContain(`POST /api/videos/${ID}/retry`))
  })

  it('R-CH-14: a failed video removed from YouTube keeps its reason but offers no Retry', async () => {
    await openWith({ status: 'failed', error_code: 'VIDEO_REMOVED', gone: true })

    expect(within(row()).getByText('Failed')).toBeTruthy()
    expect(part('[data-reason]').textContent).toBe('The video is gone from YouTube')
    expect(within(row()).getByText('Removed from YouTube')).toBeTruthy()
    expect(within(row()).queryByRole('button', { name: 'Retry' })).toBeNull()
    expect(within(row()).queryByRole('button', { name: 'Mirror' })).toBeNull()
  })

  it.each([
    ['not_downloaded', 'Mirror'],
    ['failed', 'Retry'],
  ] as const)(
    'R-CH-14: once a check finds the video on YouTube again, %s offers %s again',
    async (status, button) => {
      const app = await openWith({ status, gone: true })
      expect(within(row()).queryByRole('button', { name: button })).toBeNull()

      app.stream().videoUpdated(CHANNEL_ID, video(1, { status, gone: false }))

      await waitFor(() => expect(within(row()).getByRole('button', { name: button })).toBeTruthy())
      expect(within(row()).queryByText('Removed from YouTube')).toBeNull()
    },
  )

  it('R-DT-13: an exact date that arrives replaces the approximate one with a highlight', async () => {
    const app = await openWith({
      published_at: null,
      published_precision: 'month',
      published_around: NOW - 40 * 86_400,
    })
    expect(within(row()).getByText(/Uploaded around/)).toBeTruthy()

    app
      .stream()
      .videoUpdated(CHANNEL_ID, video(1, { status: 'synced', published_at: NOW - 30 * 86_400 }))

    await waitFor(() => expect(row().querySelector('[data-date="exact"]')).not.toBeNull())
    expect(row().querySelector('[data-arrived]')).not.toBeNull()
    expect(within(row()).queryByText(/Uploaded around/)).toBeNull()
  })

  it('R-FB-01: the channel says "Mirroring X of Y" while its videos download', async () => {
    const app = await openWith()

    app.stream().channelUpdated(channel({ status: 'mirroring', mirroring: { done: 1, total: 3 } }))

    await waitFor(() =>
      expect(within(screen.getByRole('navigation')).getByText('Mirroring 2 of 3')).toBeTruthy(),
    )
  })

  it('R-FB-03: a change of a video of another channel changes nothing here', async () => {
    const app = await openWith()

    app.stream().videoUpdated('UCanotherchannel00000000', video(1, { status: 'queued' }))

    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(within(row()).getByText('Not downloaded')).toBeTruthy()
  })
})

describe('the details panel', () => {
  function details(changes: Partial<VideoDetails> = {}): VideoDetails {
    return {
      video: video(1, { status: 'synced', height: 1080, file_size: 412_000_000 }),
      channel_id: CHANNEL_ID,
      folder: '/Users/sam/Movies/YouTube/Sample Channel',
      file: {
        name: 'Video 1.mkv',
        size: 412_000_000,
        width: 1920,
        height: 1080,
        fps: 30,
        vcodec: 'av1',
        acodec: 'opus',
        audio_channels: 2,
        subtitles: 'manual',
        cover_embedded: true,
      },
      downloaded_at: NOW - 3600,
      description: 'How I set up the workshop.',
      chapters: [
        { start_s: 0, title: 'Intro' },
        { start_s: 95, title: 'Tools' },
      ],
      thumbnail_saved: true,
      url: `https://www.youtube.com/watch?v=${ID}`,
      ...changes,
    }
  }

  it('R-QU-04: the details list each part of a running download with its size and progress', async () => {
    const app = await openWith(
      { status: 'downloading', job_id: 'J1' },
      {
        [`GET /api/videos/${ID}`]: jsonResponse(
          details({ video: video(1, { status: 'downloading', job_id: 'J1' }), file: null }),
        ),
      },
    )
    app.stream().jobProgress(
      download({
        parts: [
          { kind: 'thumbnail', size: 150_000, done: 150_000, estimated: false, finished: true },
          { kind: 'subtitles', size: 40_000, done: 40_000, estimated: false, finished: true },
          {
            kind: 'video',
            size: 410_000_000,
            done: 336_200_000,
            estimated: false,
            finished: false,
          },
          { kind: 'audio', size: 120_000_000, done: 0, estimated: true, finished: false },
        ],
      }),
    )

    await fireEvent.click(within(row()).getByRole('button', { name: 'Details of Video 1' }))

    const list = await waitFor(() => part('[data-details-parts]'))
    expect([...list.querySelectorAll('li')].map((item) => item.textContent?.trim())).toEqual([
      'Thumbnail · 150 KB · done',
      'Subtitles · 40 KB · done',
      'Video · 410 MB · 82%',
      'Audio · about 120 MB · waiting',
    ])
  })

  it('R-UI-08, R-UI-09: the title opens the details: status, file, description and chapters', async () => {
    await openWith({ status: 'synced' }, { [`GET /api/videos/${ID}`]: jsonResponse(details()) })

    await fireEvent.click(within(row()).getByRole('button', { name: 'Details of Video 1' }))

    const panel = await screen.findByRole('complementary', { name: 'Video details' })
    await waitFor(() =>
      expect(within(panel).getByRole('heading', { name: 'Video 1' })).toBeTruthy(),
    )
    expect(within(panel).getByText('Synced · 1080p')).toBeTruthy()
    expect(within(panel).getByText('English subtitles')).toBeTruthy()
    expect(within(panel).getByText('2 chapters')).toBeTruthy()
    expect(part('[data-fact="name"]').textContent).toContain('Video 1.mkv')
    expect(part('[data-fact="video"]').textContent).toContain('1920 x 1080, 30 fps, AV1')
    expect(part('[data-fact="audio"]').textContent).toContain('opus, stereo')
    expect(part('[data-fact="uploaded"]').textContent).toContain('(also set as the file date)')
    expect(part('[data-fact="thumbnail"]').textContent).toContain(
      'Embedded in the file, original image saved',
    )
    expect(part('[data-details-description]').textContent).toContain('How I set up the workshop.')
    expect(part('[data-details-chapters]').textContent).toContain('1:35')
    expect(within(panel).getByRole('button', { name: 'Play' })).toBeTruthy()
    expect(within(panel).getByRole('button', { name: 'Show in Finder' })).toBeTruthy()
    expect(within(panel).getByRole('link', { name: 'Open on YouTube' }).getAttribute('href')).toBe(
      `https://www.youtube.com/watch?v=${ID}`,
    )
    expect(
      within(panel).queryByRole('button', { name: /Copy link|Re-download|Exclude/ }),
    ).toBeNull()
    expect(row().getAttribute('data-open')).toBe('true')
  })

  it('R-UI-08: Esc closes the details', async () => {
    await openWith({}, { [`GET /api/videos/${ID}`]: jsonResponse(details({ file: null })) })
    await fireEvent.click(within(row()).getByRole('button', { name: 'Details of Video 1' }))
    await screen.findByRole('complementary', { name: 'Video details' })

    await fireEvent.keyDown(window, { key: 'Escape' })

    await waitFor(() =>
      expect(screen.queryByRole('complementary', { name: 'Video details' })).toBeNull(),
    )
  })

  it('R-MI-01, R-UI-09: the details of a video that is not downloaded offer Mirror', async () => {
    const app = await openWith(
      {},
      {
        [`GET /api/videos/${ID}`]: jsonResponse(
          details({ video: video(1), file: null, description: null, chapters: [] }),
        ),
      },
    )
    await fireEvent.click(within(row()).getByRole('button', { name: 'Details of Video 1' }))
    const panel = await screen.findByRole('complementary', { name: 'Video details' })

    await fireEvent.click(await within(panel).findByRole('button', { name: 'Mirror' }))

    await waitFor(() =>
      expect(app.lastBody('/api/videos/mirror')).toEqual({ ids: [ID], first: false }),
    )
    expect(part('[data-details-description]').textContent).toContain(
      'The description is saved with the file when the video is mirrored.',
    )
  })

  it('R-CH-14, R-UI-09: the details of a video removed from YouTube offer no Mirror', async () => {
    const gone = video(1, { gone: true })
    await openWith(
      { gone: true },
      {
        [`GET /api/videos/${ID}`]: jsonResponse(
          details({ video: gone, file: null, description: null, chapters: [] }),
        ),
      },
    )
    await fireEvent.click(within(row()).getByRole('button', { name: 'Details of Video 1' }))
    const panel = await screen.findByRole('complementary', { name: 'Video details' })

    await within(panel).findByRole('link', { name: 'Open on YouTube' })
    expect(within(panel).queryByRole('button', { name: 'Mirror' })).toBeNull()
  })
})

describe('a video whose file is gone', () => {
  it('R-MI-06: it says "File missing" and offers "Mirror again", not Play', async () => {
    await openWith({ status: 'file_missing' })

    expect(within(row()).getByText('File missing')).toBeTruthy()
    expect(within(row()).getByRole('button', { name: 'Mirror again' })).toBeTruthy()
    expect(within(row()).queryByRole('button', { name: 'Play' })).toBeNull()
  })

  it('R-MI-06, R-UI-10: Play on a file deleted since the last check says the file is gone', async () => {
    await openWith(
      { status: 'synced', height: 1080, file_size: 412_000_000 },
      { [`POST /api/videos/${ID}/play`]: jsonResponse(errorBody('FILE_MISSING'), 404) },
    )

    await fireEvent.click(within(row()).getByRole('button', { name: 'Play' }))

    expect(await screen.findByText(/no longer in its folder/)).toBeTruthy()
    expect(screen.queryByText(/The folder cannot be used/)).toBeNull()
  })
})

describe('one progress for the whole Mirror', () => {
  it('R-QU-04: sizes in MB, and no time left until the speed is stable', async () => {
    const app = await openWith()
    app.stream().videoUpdated(CHANNEL_ID, video(1, { status: 'downloading', job_id: 'J1' }))

    app.stream().jobProgress(
      download({
        fraction: 0.62,
        downloaded_bytes: 340_000_000,
        total_bytes: 550_000_000,
        left_s: null,
      }),
    )

    await waitFor(() => expect(within(row()).getByText('Downloading 62%')).toBeTruthy())
    expect(part('[data-progress-facts]').textContent).toBe('340 of 550 MB')
  })

  it('R-QU-04, R-MD-04: a second download without subtitles says so', async () => {
    const app = await openWith()
    app.stream().videoUpdated(CHANNEL_ID, video(1, { status: 'downloading', job_id: 'J1' }))

    app.stream().jobProgress(download({ again: true, left_s: null }))

    await waitFor(() =>
      expect(part('[data-progress-facts]').textContent).toContain(
        'Downloading again without subtitles',
      ),
    )
  })
})
