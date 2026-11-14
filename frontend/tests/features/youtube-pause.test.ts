import { fireEvent, screen, waitFor, within } from '@testing-library/vue'
import { describe, expect, it } from 'vitest'

import { appState, channel, NOW } from '../helpers/catalogue'
import { openApp, part } from '../helpers/app'
import { jsonResponse } from '../helpers/fetch'

/** 14 Nov 2026, 06:57 UTC: a quarter of an hour after the "now" of the tests. */
const pause = { code: 'BOT_CHECK', until: NOW + 900 } as const

describe('the banner of the "not a bot" check', () => {
  it('R-ER-05: one banner says what the check is, what it depends on, when the app tries again and what to try', async () => {
    await openApp({ channels: [channel()], state: { youtube_pause: pause } })

    const banner = part('[data-banner="youtube-pause"]')
    expect(banner.textContent).toContain('YouTube asks to confirm that you are not a bot')
    expect(banner.textContent).toContain('for some network addresses')
    expect(banner.textContent).toContain('tries again at 06:57')
    expect(banner.textContent).toContain('another network or another VPN location')
    expect(document.querySelectorAll('[data-banner="youtube-pause"]')).toHaveLength(1)
  })

  it('R-ER-05: the check is no error of a channel', async () => {
    await openApp({ channels: [channel()], state: { youtube_pause: pause } })

    await screen.findByRole('heading', { level: 1, name: 'Sample Channel' })
    expect(document.querySelector('[data-banner="check-failed"]')).toBeNull()
  })

  it('R-FB-04: the banner appears when the pause begins and goes when it ends', async () => {
    const app = await openApp({ channels: [channel()] })
    expect(document.querySelector('[data-banner="youtube-pause"]')).toBeNull()

    app.stream().pauseChanged(pause)
    await waitFor(() => expect(part('[data-banner="youtube-pause"]')).toBeTruthy())
    app.stream().pauseChanged(null)

    await waitFor(() => expect(document.querySelector('[data-banner="youtube-pause"]')).toBeNull())
  })

  it('R-ER-05: "Try now" ends the pause, and the banner goes', async () => {
    const app = await openApp({
      channels: [channel()],
      state: { youtube_pause: pause },
      answers: { 'POST /api/youtube/try-now': jsonResponse(appState({ channels: [channel()] })) },
    })

    await fireEvent.click(
      within(part('[data-banner="youtube-pause"]')).getByRole('button', { name: 'Try now' }),
    )

    await waitFor(() => expect(document.querySelector('[data-banner="youtube-pause"]')).toBeNull())
    expect(app.requests()).toContain('POST /api/youtube/try-now')
  })
})
