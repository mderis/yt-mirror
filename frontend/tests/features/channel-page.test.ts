import { fireEvent, screen, waitFor, within } from '@testing-library/vue'
import { describe, expect, it } from 'vitest'

import { noContent, openApp, part } from '../helpers/app'
import { channel, CHANNEL_ID, NOW, video } from '../helpers/catalogue'
import { errorBody, jsonResponse } from '../helpers/fetch'

const VIDEOS = `GET /api/channels/${CHANNEL_ID}/videos`
const CHECK = `POST /api/channels/${CHANNEL_ID}/check`

function row(number: number): HTMLElement {
  return part(`[data-video="${video(number).id}"]`)
}

/** Wait until the page of the sample channel is open. */
async function page(): Promise<HTMLElement> {
  return screen.findByRole('heading', { level: 1, name: 'Sample Channel' })
}

/** The rows of the video list. */
function rows(): HTMLElement[] {
  return within(screen.getByRole('list', { name: 'Videos' })).queryAllByRole('listitem')
}

/** The text of a line of facts, with one space around every separator. */
function line(element: Element | null): string {
  return (element?.textContent ?? '')
    .replace(/\s*·\s*/g, ' · ')
    .replace(/\s+/g, ' ')
    .trim()
}

describe('the channel page', () => {
  it('R-CH-35: the header shows the totals, the result of the last check and both times', async () => {
    await openApp({
      channels: [
        channel({
          videos: 1248,
          synced: 212,
          excluded: 5,
          size_bytes: 41_240_000_000,
          last_check_at: NOW - 125,
          last_full_check_at: NOW - 3 * 86_400,
        }),
      ],
    })
    await page()

    expect(line(part('[data-totals]'))).toBe('1,248 videos · 212 synced · 5 excluded · 41.2 GB')
    expect(line(part('[data-check]'))).toBe('Checked 2 min ago · Full check 3 days ago')
  })

  it('R-CH-35: the result of the last check says how many videos are new', async () => {
    await openApp({
      channels: [channel({ status: 'new_videos', new_videos: 3, last_check_at: NOW })],
    })
    await page()

    expect(part('[data-check]').textContent).toContain('Checked just now, 3 new videos')
  })

  it('R-CH-10: the list shows thumbnail, duration, title, date, views and status of every video', async () => {
    await openApp({
      channels: [channel({ pictures: 2 })],
      videos: [
        video(1, {
          title: 'Building a cabin',
          duration_s: 1458,
          view_count: 48_000,
          published_at: 1_794_433_200,
        }),
        video(2),
      ],
    })

    await page()
    await waitFor(() => expect(rows()).toHaveLength(2))
    const first = row(1)
    expect(first.querySelector('img')?.getAttribute('src')).toBe(
      `/api/videos/${video(1).id}/thumbnail`,
    )
    expect(first.querySelector('[data-duration]')?.textContent?.trim()).toBe('24:18')
    expect(first.querySelector('[data-title]')?.textContent).toBe('Building a cabin')
    expect(line(first.querySelector('[data-facts]'))).toBe('Uploaded 11 Nov 2026 · 48K views')
    expect(within(first).getByText('Not downloaded')).toBeTruthy()
  })

  it('R-CH-10, R-CH-16: a thumbnail that was not cached yet is asked for again when more pictures are cached', async () => {
    const app = await openApp({
      channels: [channel({ pictures: 2 })],
      videos: [video(1), video(2)],
    })
    await waitFor(() => row(2))
    const loaded = row(2).querySelector('img')?.getAttribute('src')

    await fireEvent.error(row(1).querySelector('img') as HTMLImageElement)
    const whileMissing = row(1).querySelector('img')
    app.stream().channelUpdated(channel({ pictures: 3 }))

    await waitFor(() =>
      expect(row(1).querySelector('img')?.getAttribute('src')).toBe(
        `/api/videos/${video(1).id}/thumbnail?v=3`,
      ),
    )
    expect(whileMissing).toBeNull()
    expect(row(2).querySelector('img')?.getAttribute('src')).toBe(loaded)

    await fireEvent.error(row(1).querySelector('img') as HTMLImageElement)
    app.stream().channelUpdated(channel({ pictures: 4 }))

    await waitFor(() =>
      expect(row(1).querySelector('img')?.getAttribute('src')).toBe(
        `/api/videos/${video(1).id}/thumbnail?v=4`,
      ),
    )
  })

  it('R-UI-13: the video list is a named region that can be focused, so the keyboard can scroll it', async () => {
    await openApp({ channels: [channel()], videos: [video(1)] })
    await waitFor(() => row(1))

    const region = screen.getByRole('region', { name: 'Video list' })
    expect(region.getAttribute('tabindex')).toBe('0')
    expect(within(region).getByRole('list', { name: 'Videos' })).toBeTruthy()
  })

  it('R-CH-10: a video without duration or views shows neither and nothing made up', async () => {
    await openApp({
      channels: [channel()],
      videos: [video(1, { duration_s: null, view_count: null })],
    })
    await waitFor(() => row(1))

    expect(row(1).querySelector('[data-duration]')).toBeNull()
    expect(row(1).querySelector('[data-facts]')?.textContent).not.toContain('views')
  })

  it('R-DT-04, R-DT-13: an approximate date is shown as far as its precision allows, as a placeholder', async () => {
    const around = 1_794_433_200
    await openApp({
      channels: [channel()],
      videos: [
        video(1, { published_at: around, published_precision: 'year', published_around: around }),
        video(2, { published_at: around, published_precision: 'month', published_around: around }),
        video(3, { published_at: around, published_precision: 'week', published_around: around }),
        video(4),
      ],
    })
    await waitFor(() => row(4))

    const dates = [1, 2, 3].map((number) => part(`[data-video="${video(number).id}"] [data-date]`))
    expect(dates.map((date) => date.querySelector('span:not(.sr-only)')?.textContent)).toEqual([
      'Uploaded around 2026',
      'Uploaded around Nov 2026',
      'Uploaded around 11 Nov 2026',
    ])
    expect(dates.every((date) => date.getAttribute('data-date') === 'waiting')).toBe(true)
    expect(dates.every((date) => date.getAttribute('title') === 'Exact date pending')).toBe(true)
    expect(row(4).querySelector('[data-date]')?.getAttribute('data-date')).toBe('exact')
  })

  it('R-DT-04: a video for which the listing gave no date shows "date pending" and no date', async () => {
    await openApp({ channels: [channel()], videos: [video(1, { published_at: null })] })
    await waitFor(() => row(1))

    expect(row(1).querySelector('[data-date] span:not(.sr-only)')?.textContent).toBe('date pending')
  })

  it('R-CH-15: a new video carries the "New" tag, the others do not', async () => {
    await openApp({ channels: [channel()], videos: [video(1, { is_new: true }), video(2)] })
    await waitFor(() => row(2))

    expect(within(row(1)).getByText('New')).toBeTruthy()
    expect(within(row(2)).queryByText('New')).toBeNull()
  })

  it('R-CH-14: a removed video stays in the list with a "Removed from YouTube" marker', async () => {
    await openApp({ channels: [channel()], videos: [video(1), video(2, { gone: true })] })
    await waitFor(() => row(2))

    expect(within(row(2)).getByText('Removed from YouTube')).toBeTruthy()
    expect(within(row(1)).queryByText('Removed from YouTube')).toBeNull()
  })

  it('R-CH-11: a first listing shows how many videos were found so far, and that the app can be used', async () => {
    const listing = channel({
      status: 'checking',
      first_listed_at: null,
      last_check_at: null,
      last_full_check_at: null,
      videos: 0,
    })
    const app = await openApp({ channels: [listing] })
    await page()
    const before = part('[data-listing]').textContent?.trim()

    app
      .stream()
      .taskProgress({ channel_id: CHANNEL_ID, kind: 'first_listing', done: 120, total: null })

    expect(before).toBe('Reading the video list from YouTube...')
    await waitFor(() =>
      expect(part('[data-listing]').textContent?.trim()).toBe(
        'Reading the video list from YouTube: 120 videos found so far...',
      ),
    )
    expect(
      screen.getByText('Large channels can take a minute. You can keep using the app.'),
    ).toBeTruthy()
    expect(screen.getByRole('progressbar', { name: 'Progress of the video list' })).toBeTruthy()
    expect(
      document.querySelectorAll('[data-skeleton-list] [data-skeleton]').length,
    ).toBeGreaterThan(0)
    expect(screen.queryByRole('button', { name: 'Check now' })).toBeNull()
  })

  it('R-CH-11: when the first listing is done, the list takes the place of its progress', async () => {
    const listing = channel({
      status: 'checking',
      first_listed_at: null,
      last_check_at: null,
      videos: 0,
    })
    const answers = [jsonResponse({ videos: [] }), jsonResponse({ videos: [video(1), video(2)] })]
    const app = await openApp({
      channels: [listing],
      answers: { [VIDEOS]: () => answers.shift() as Response },
    })
    await page()

    app
      .stream()
      .channelUpdated(
        channel({ videos: 2, first_listed_at: NOW, last_check_at: NOW, catalogue_version: 2 }),
      )

    await waitFor(() => expect(rows()).toHaveLength(2))
    expect(document.querySelector('[data-listing]')).toBeNull()
    expect(part('[data-totals]').textContent).toContain('2 videos')
  })

  it('R-CH-25: a failed check shows a banner with a retry button and keeps the list', async () => {
    const failed = channel({
      status: 'could_not_check',
      last_check_error: 'NETWORK_UNREACHABLE',
      last_check_at: 1_794_433_200,
    })
    const app = await openApp({
      channels: [failed],
      videos: [video(1), video(2)],
      answers: { [CHECK]: jsonResponse({ ...failed, status: 'checking' }) },
    })
    await waitFor(() => row(2))

    const banner = part('[data-banner="check-failed"]')
    expect(banner.getAttribute('role')).toBe('alert')
    expect(banner.textContent).toContain('Could not reach YouTube')
    expect(banner.textContent).toContain(
      'The video list below is from the last successful check (11 Nov 2026, 21:40). Your downloaded files are not affected.',
    )
    expect(part('[data-check]').textContent).toContain('Last check failed')
    await fireEvent.click(within(banner).getByRole('button', { name: 'Try again' }))
    await waitFor(() =>
      expect(app.lastBody(`/api/channels/${CHANNEL_ID}/check`)).toEqual({ kind: 'quick' }),
    )
    expect(rows()).toHaveLength(2)
  })

  it('R-CH-25, R-ER-02: the banner of a failed check has the words of its error code', async () => {
    await openApp({
      channels: [channel({ status: 'could_not_check', last_check_error: 'RATE_LIMITED' })],
    })
    await page()

    const banner = part('[data-banner="check-failed"]')
    expect(banner.textContent).toContain('YouTube asked yt-mirror to slow down.')
    expect(banner.textContent).toContain('Wait a few minutes, then try again.')
  })

  it('R-CH-25: a first listing that failed says that there is no list yet, and can be tried again', async () => {
    await openApp({
      channels: [
        channel({
          status: 'could_not_check',
          last_check_error: 'NETWORK_UNREACHABLE',
          first_listed_at: null,
          last_check_at: null,
          last_full_check_at: null,
          videos: 0,
        }),
      ],
    })
    await page()

    const banner = part('[data-banner="check-failed"]')
    expect(banner.textContent).toContain('The video list could not be read yet.')
    expect(within(banner).getByRole('button', { name: 'Try again' })).toBeTruthy()
    expect(document.querySelector('[data-listing]')).toBeNull()
  })

  it('R-CH-27: a full check shows its progress against the size of the catalogue and can be cancelled', async () => {
    const progress = {
      channel_id: CHANNEL_ID,
      kind: 'full_check',
      done: 1200,
      total: 6600,
    } as const
    const app = await openApp({
      channels: [channel({ status: 'checking', videos: 6600, progress })],
      answers: {
        [`POST /api/channels/${CHANNEL_ID}/check/cancel`]: jsonResponse({ cancelled: true }),
      },
    })
    await page()

    const block = part('[data-full-check]')
    expect(within(block).getByRole('status').textContent).toBe('Full check: 1,200 of about 6,600')
    expect(
      within(block)
        .getByRole('progressbar', { name: 'Progress of the full check' })
        .getAttribute('aria-valuenow'),
    ).toBe('18')
    await fireEvent.click(within(block).getByRole('button', { name: 'Cancel' }))
    await waitFor(() =>
      expect(app.requests()).toContain(`POST /api/channels/${CHANNEL_ID}/check/cancel`),
    )
  })

  it('R-CH-27: the progress of a full check follows the events, and goes when the check ends', async () => {
    const app = await openApp({ channels: [channel({ status: 'checking' })] })
    await page()

    app.stream().taskProgress({ channel_id: CHANNEL_ID, kind: 'full_check', done: 30, total: null })
    await waitFor(() => expect(part('[data-full-check]').textContent).toContain('Full check: 30'))
    app.stream().taskProgress({ channel_id: CHANNEL_ID, kind: 'full_check', done: 60, total: 12 })
    await waitFor(() =>
      expect(part('[data-full-check]').textContent).toContain('Full check: 60 of about 12'),
    )
    const full = screen
      .getByRole('progressbar', { name: 'Progress of the full check' })
      .getAttribute('aria-valuenow')
    app.stream().channelUpdated(channel({ last_check_at: NOW, last_full_check_at: NOW }))

    expect(full).toBe('100')
    await waitFor(() => expect(document.querySelector('[data-full-check]')).toBeNull())
  })

  it('R-CH-23, R-UI-11: "Check now" starts a quick check and is busy while the channel is checked', async () => {
    const app = await openApp({
      channels: [channel()],
      answers: { [CHECK]: jsonResponse(channel({ status: 'checking' })) },
    })
    const button = await screen.findByRole('button', { name: 'Check now' })

    await fireEvent.click(button)
    app.stream().channelUpdated(channel({ status: 'checking' }))

    await waitFor(() => expect(button.getAttribute('aria-busy')).toBe('true'))
    expect(app.lastBody(`/api/channels/${CHANNEL_ID}/check`)).toEqual({ kind: 'quick' })
    expect(part('[data-check]').textContent).toContain('Checking for new videos...')
  })

  it('R-CH-31: a paused channel says that it is not checked, and offers no "Check now"', async () => {
    await openApp({ channels: [channel({ paused: true, status: 'paused' })] })
    await page()

    expect(part('[data-check]').textContent).toContain('Paused. No checks until you resume.')
    expect(screen.queryByRole('button', { name: 'Check now' })).toBeNull()
  })

  it('R-CH-30: "Open folder" asks to show the folder of the channel in Finder', async () => {
    const app = await openApp({
      channels: [channel()],
      answers: { [`POST /api/channels/${CHANNEL_ID}/open-folder`]: noContent() },
    })

    await fireEvent.click(await screen.findByRole('button', { name: 'Open folder' }))

    await waitFor(() =>
      expect(app.requests()).toContain(`POST /api/channels/${CHANNEL_ID}/open-folder`),
    )
  })

  it('R-CH-30, R-UI-13: "More actions" opens the menu of the channel, and a second press closes it', async () => {
    await openApp({ channels: [channel()] })
    const button = await screen.findByRole('button', { name: 'More actions' })

    await fireEvent.click(button)
    const menu = await screen.findByRole('menu', { name: 'Actions of Sample Channel' })
    const items = within(menu)
      .getAllByRole('menuitem')
      .map((entry) => entry.textContent?.trim())
    await fireEvent.mouseDown(button)
    await fireEvent.click(button)

    expect(items).toContain('Full check')
    expect(items).toContain('Remove channel')
    await waitFor(() => expect(screen.queryByRole('menu')).toBeNull())
  })

  it('R-ER-02, R-ER-03: a list that cannot be loaded says so and can be loaded again', async () => {
    const answers = [jsonResponse(errorBody('INTERNAL'), 500), jsonResponse({ videos: [video(1)] })]
    await openApp({
      channels: [channel()],
      answers: { [VIDEOS]: () => answers.shift() as Response },
    })

    const banner = await waitFor(() => part('[data-banner="list-failed"]'))
    expect(banner.textContent).toContain('The video list could not be loaded.')
    expect(banner.textContent).toContain('Something unexpected went wrong inside yt-mirror.')
    await fireEvent.click(within(banner).getByRole('button', { name: 'Try again' }))

    await waitFor(() => expect(rows()).toHaveLength(1))
    expect(document.querySelector('[data-banner="list-failed"]')).toBeNull()
  })
})
