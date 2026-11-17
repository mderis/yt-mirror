import { fireEvent, screen, waitFor, within } from '@testing-library/vue'
import { describe, expect, it } from 'vitest'

import { openApp, part } from '../helpers/app'
import { channel, CHANNEL_ID, NOW, video } from '../helpers/catalogue'
import { jsonResponse } from '../helpers/fetch'

const approximate = {
  published_at: null,
  published_precision: 'year',
  published_around: NOW,
} as const

/** The status line of the channel in the sidebar. */
function sidebarStatus(): string {
  return part('nav[aria-label="Channels"] li').textContent ?? ''
}

describe('the date of a video while its exact date is fetched', () => {
  it('R-DT-13: the list tells waiting, updating and unavailable dates apart, with their notes', async () => {
    await openApp({
      channels: [channel()],
      videos: [
        video(1, approximate),
        video(2, { ...approximate, date: { state: 'updating', reason: null, retry_at: null } }),
        video(3, {
          ...approximate,
          date: { state: 'unavailable', reason: 'VIDEO_PRIVATE', retry_at: NOW + 3600 },
        }),
      ],
      route: `/channels/${CHANNEL_ID}`,
    })

    await screen.findByText('Video 3')
    const dateOf = (number: number): HTMLElement =>
      part(`[data-video="${video(number).id}"] [data-date]`)
    expect(dateOf(1).getAttribute('data-date')).toBe('waiting')
    expect(dateOf(1).getAttribute('title')).toBe('Exact date pending')
    expect(dateOf(2).getAttribute('data-date')).toBe('updating')
    expect(dateOf(2).getAttribute('title')).toBe('Getting the exact date...')
    expect(dateOf(3).getAttribute('data-date')).toBe('unavailable')
    expect(dateOf(3).getAttribute('title')).toBe(
      'The video is private. It is tried again at 07:42.',
    )
  })

  it('R-DT-13: a date held back by YouTube says so, and later', async () => {
    await openApp({
      channels: [channel()],
      videos: [
        video(1, {
          ...approximate,
          date: { state: 'unavailable', reason: 'RATE_LIMITED', retry_at: null },
        }),
      ],
      route: `/channels/${CHANNEL_ID}`,
    })

    const label = await waitFor(() => part(`[data-video="${video(1).id}"] [data-date]`))
    expect(label.getAttribute('title')).toBe(
      'YouTube asked yt-mirror to slow down. It is tried again later.',
    )
  })
})

describe('the status of a channel whose exact dates are fetched', () => {
  it('R-FB-01, R-DT-14: "Exact dates X of Y" with the measured time left', async () => {
    await openApp({
      channels: [
        channel({
          status: 'exact_dates',
          exact_dates: { done: 340, total: 1000, left_s: 3000, offer_key: true },
        }),
      ],
    })

    expect(sidebarStatus()).toContain('Exact dates 340 of 1,000 · about 50 minutes left')
  })

  it('R-DT-14: no time is shown before it was measured', async () => {
    await openApp({
      channels: [
        channel({
          status: 'exact_dates',
          exact_dates: { done: 2, total: 1000, left_s: null, offer_key: false },
        }),
      ],
    })

    expect(sidebarStatus()).toContain('Exact dates 2 of 1,000')
    expect(sidebarStatus()).not.toContain('left')
  })

  it('R-FB-01: dates held back by YouTube wait, with when they go on', async () => {
    await openApp({
      channels: [channel({ status: 'waiting_for_youtube', waiting_until: NOW + 900 })],
    })

    const item = part('nav[aria-label="Channels"] li')
    expect(item.textContent).toContain('Waiting for YouTube')
    expect(item.innerHTML).toContain('The next attempt is at 06:57.')
  })

  it('R-CH-25: a failed check says when it is retried', async () => {
    await openApp({
      channels: [
        channel({
          status: 'could_not_check',
          last_check_error: 'NETWORK_UNREACHABLE',
          last_check_error_at: NOW - 60,
          retry_at: NOW + 240,
        }),
      ],
    })

    expect(sidebarStatus()).toContain('Could not check · retrying in 4 min')
  })

  it('R-CH-25: the banner of a failed check names the time of the automatic retry', async () => {
    await openApp({
      channels: [
        channel({
          status: 'could_not_check',
          last_check_error: 'NETWORK_UNREACHABLE',
          last_check_error_at: NOW - 60,
          retry_at: NOW + 240,
        }),
      ],
      route: `/channels/${CHANNEL_ID}`,
    })

    const banner = await waitFor(() => part('[data-banner="check-failed"]'))
    expect(banner.textContent).toContain('yt-mirror tries again by itself at 06:46.')
  })
})

describe('the exact dates in the header of the channel page', () => {
  it('R-FB-01, D-086: the progress is in the header while the sidebar tells new videos', async () => {
    await openApp({
      channels: [
        channel({
          status: 'new_videos',
          new_videos: 2,
          exact_dates: { done: 340, total: 1000, left_s: 3000, offer_key: true },
        }),
      ],
      route: `/channels/${CHANNEL_ID}`,
    })

    const header = await waitFor(() => part('[data-exact-dates]'))
    expect(header.textContent).toContain('Exact dates 340 of 1,000 · about 50 minutes left')
    expect(sidebarStatus()).toContain('2 new videos')
  })

  it('R-FB-01: exact dates held back by YouTube say so in the header, with until when', async () => {
    await openApp({
      channels: [
        channel({
          status: 'waiting_for_youtube',
          waiting_until: NOW + 900,
          exact_dates: { done: 3, total: 10, left_s: null, offer_key: false },
        }),
      ],
      route: `/channels/${CHANNEL_ID}`,
    })

    const header = await waitFor(() => part('[data-exact-dates]'))
    expect(header.textContent).toContain('Exact dates 3 of 10 · waiting for YouTube until 06:57')
  })

  it('R-FB-01: without dates waiting the header says nothing of them', async () => {
    await openApp({ channels: [channel()], route: `/channels/${CHANNEL_ID}` })

    await screen.findByRole('heading', { level: 1, name: 'Sample Channel' })
    expect(document.querySelector('[data-exact-dates]')).toBeNull()
  })
})

describe('the optional API key', () => {
  it('R-DT-15: a long fetch without a key offers the key with the measured time', async () => {
    await openApp({
      channels: [
        channel({
          status: 'exact_dates',
          exact_dates: { done: 10, total: 1000, left_s: 3 * 3600, offer_key: true },
        }),
      ],
      route: `/channels/${CHANNEL_ID}`,
    })

    const offer = await waitFor(() => part('[data-banner="key-offer"]'))
    expect(offer.textContent).toContain('Exact dates take about 3 hours left at this pace')
    expect(offer.textContent).toContain('one request per 50 videos')
    expect(document.querySelector('[data-dialog="api-key"]')).toBeNull()
  })

  it('R-DT-12: a key that is not working shows a notice that opens the guide, never a dialog by itself', async () => {
    await openApp({
      channels: [
        channel({
          status: 'exact_dates',
          key_notice: true,
          exact_dates: { done: 10, total: 100, left_s: 900, offer_key: false },
        }),
      ],
      state: { api_key: { status: 'invalid', until: null } },
      route: `/channels/${CHANNEL_ID}`,
    })

    const notice = await waitFor(() => part('[data-banner="key-notice"]'))
    expect(notice.textContent).toContain(
      'Exact dates: the API key is not working, using the slow way.',
    )
    expect(document.querySelector('[data-dialog="api-key"]')).toBeNull()

    await fireEvent.click(within(notice).getByRole('button', { name: 'Fix the key' }))

    const dialog = await waitFor(() => part('[data-dialog="api-key"]'))
    expect(dialog.textContent).toContain('YouTube did not accept the saved key.')
  })

  it('R-DT-12: an unreadable key says so in the guide, with a way to save it again', async () => {
    await openApp({
      channels: [
        channel({
          key_notice: true,
          exact_dates: { done: 0, total: 5, left_s: null, offer_key: false },
        }),
      ],
      state: { api_key: { status: 'unreadable', until: null } },
      route: `/channels/${CHANNEL_ID}`,
    })
    await fireEvent.click(await screen.findByRole('button', { name: 'Fix the key' }))

    expect(part('[data-key-status="unreadable"]').textContent).toContain(
      'Key saved but cannot be read. Paste it again and save it.',
    )
    expect(screen.getByRole('button', { name: 'Save key' })).toBeTruthy()
  })

  it('R-DT-12: a used-up quota says until when the app does without the key', async () => {
    await openApp({
      channels: [
        channel({
          key_notice: true,
          exact_dates: { done: 0, total: 5, left_s: null, offer_key: false },
        }),
      ],
      state: { api_key: { status: 'quota_exceeded', until: NOW + 7200 } },
      route: `/channels/${CHANNEL_ID}`,
    })
    await fireEvent.click(await screen.findByRole('button', { name: 'Fix the key' }))

    expect(part('[data-key-status="quota_exceeded"]').textContent).toContain('until 08:42')
  })

  it('R-DT-12: the guide says the key is free, tests a pasted key and saves it', async () => {
    const app = await openApp({
      channels: [
        channel({
          status: 'exact_dates',
          exact_dates: { done: 10, total: 1000, left_s: 3 * 3600, offer_key: true },
        }),
      ],
      route: `/channels/${CHANNEL_ID}`,
      answers: {
        'POST /api/settings/api-key/test': jsonResponse({
          works: true,
          error_code: null,
          api_key: { status: 'none', until: null },
        }),
        'PUT /api/settings/api-key': jsonResponse({ status: 'saved', until: null }),
      },
    })
    await fireEvent.click(await screen.findByRole('button', { name: 'Get exact dates faster' }))
    const dialog = part('[data-dialog="api-key"]')
    expect(dialog.textContent).toContain('The key is free.')
    expect(dialog.textContent).toContain('you do not enter any payment details')
    expect(dialog.textContent).toContain('The key is stored only on this Mac.')

    await fireEvent.update(within(dialog).getByLabelText('Paste it here'), '  pasted-key-0001 ')
    await fireEvent.click(within(dialog).getByRole('button', { name: 'Test key' }))
    await waitFor(() =>
      expect(part('[data-key-test]').textContent).toContain(
        'Key works. Exact dates will now load quickly.',
      ),
    )
    expect(app.lastBody('/api/settings/api-key/test')).toEqual({ key: 'pasted-key-0001' })

    await fireEvent.click(screen.getByRole('button', { name: 'Save key' }))

    await waitFor(() => expect(document.querySelector('[data-dialog="api-key"]')).toBeNull())
    expect(app.lastBody('/api/settings/api-key')).toEqual({ key: 'pasted-key-0001' })
  })

  it('R-DT-12: a key YouTube refuses says why', async () => {
    await openApp({
      channels: [channel()],
      state: { youtube_pause: { code: 'BOT_CHECK', until: NOW + 900 } },
      answers: {
        'POST /api/settings/api-key/test': jsonResponse({
          works: false,
          error_code: 'API_KEY_INVALID',
          api_key: { status: 'none', until: null },
        }),
      },
    })
    await fireEvent.click(await screen.findByRole('button', { name: 'Set up the API key' }))
    const dialog = part('[data-dialog="api-key"]')

    await fireEvent.update(within(dialog).getByLabelText('Paste it here'), 'wrong')
    await fireEvent.click(within(dialog).getByRole('button', { name: 'Test key' }))

    await waitFor(() =>
      expect(part('[data-key-test]').textContent).toContain('YouTube did not accept this key.'),
    )
  })

  it('R-DT-12: a saved key can be removed', async () => {
    const app = await openApp({
      channels: [
        channel({
          key_notice: true,
          exact_dates: { done: 0, total: 5, left_s: null, offer_key: false },
        }),
      ],
      state: { api_key: { status: 'invalid', until: null } },
      route: `/channels/${CHANNEL_ID}`,
      answers: { 'DELETE /api/settings/api-key': jsonResponse({ status: 'none', until: null }) },
    })
    await fireEvent.click(await screen.findByRole('button', { name: 'Fix the key' }))

    await fireEvent.click(screen.getByRole('button', { name: 'Remove key' }))

    await waitFor(() => expect(app.requests()).toContain('DELETE /api/settings/api-key'))
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Remove key' })).toBeNull())
  })

  it('R-ER-05: the "not a bot" banner says the key gets exact dates without the check', async () => {
    await openApp({
      channels: [channel()],
      state: { youtube_pause: { code: 'BOT_CHECK', until: NOW + 900 } },
    })

    const banner = part('[data-banner="youtube-pause"]')
    expect(banner.textContent).toContain(
      'The optional API key gets exact dates without this check.',
    )
    expect(within(banner).getByRole('button', { name: 'Set up the API key' })).toBeTruthy()
  })

  it('R-DT-12: the key state follows the event stream', async () => {
    const app = await openApp({
      channels: [channel()],
      state: { youtube_pause: { code: 'BOT_CHECK', until: NOW + 900 } },
    })

    app.stream().apiKeyChanged({ status: 'saved', until: null })

    await waitFor(() =>
      expect(screen.queryByRole('button', { name: 'Set up the API key' })).toBeNull(),
    )
  })
})

describe('checks the app starts by itself', () => {
  it('R-CH-20: the sidebar says "Checking channels: 3 of 5" while all channels are checked', async () => {
    const app = await openApp({
      channels: [channel()],
      state: { checking_all: { done: 2, total: 5 } },
    })

    expect(part('[data-checking-all]').textContent).toContain('Checking channels: 3 of 5')

    app.stream().checksProgress(null)

    await waitFor(() => expect(document.querySelector('[data-checking-all]')).toBeNull())
  })
})

describe('Repair dates', () => {
  it('R-DT-09: the channel menu repairs the dates of a channel and says what it did', async () => {
    const app = await openApp({
      channels: [channel()],
      route: `/channels/${CHANNEL_ID}`,
      answers: {
        [`POST /api/channels/${CHANNEL_ID}/repair-dates`]: jsonResponse({
          checked: 12,
          repaired: 1,
          failed: 0,
        }),
      },
    })
    await fireEvent.contextMenu(part('nav[aria-label="Channels"] li button'))

    await fireEvent.click(await screen.findByRole('menuitem', { name: 'Repair dates' }))

    const done = await waitFor(() => part('[data-banner="repaired"]'))
    expect(done.textContent).toContain(
      'Dates checked: 1 of 12 files of Sample Channel were set to their published time.',
    )
    expect(app.requests()).toContain(`POST /api/channels/${CHANNEL_ID}/repair-dates`)
  })
})
