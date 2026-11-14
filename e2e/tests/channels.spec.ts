import { existsSync } from 'node:fs'
import { join } from 'node:path'

import AxeBuilder from '@axe-core/playwright'
import type { Locator, Page } from '@playwright/test'

import { expect, test, type FreshApp } from './fresh-app'

/**
 * Channels and their catalogue (docs/TESTING.md section 6, flows 2 and 3),
 * against the fake YouTube of `fixtures/youtube`. Every test starts an app of
 * its own, past its first run, with a library folder of its own.
 */
test.describe.configure({ mode: 'serial' })

const SMALL_ID = 'UCsmallchannel0000000001'
const CHANGING_ID = 'UCchangingchannel0000005'

const sidebar = (page: Page): Locator => page.getByRole('navigation', { name: 'Channels' })
const rows = (page: Page): Locator =>
  page.getByRole('list', { name: 'Videos' }).getByRole('listitem')
const row = (page: Page, videoId: string): Locator => page.locator(`[data-video="${videoId}"]`)
const dialog = (page: Page): Locator => page.getByRole('dialog')

/** Open the app past its first run. Without channels it shows the welcome screen. */
async function openApp(page: Page, app: FreshApp): Promise<void> {
  await app.finishSetup()
  await page.goto(app.firstUrl)
  await expect(sidebar(page)).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
}

/** Add a channel through the API, as the dialog would, and wait for its first listing. */
async function addChannel(app: FreshApp, handle: string, channelId: string): Promise<void> {
  await app.send('POST', '/channels/lookup', { text: handle })
  await app.send('POST', '/channels', { channel_id: channelId, auto_mirror: false })
  await checked(app, channelId)
}

/** Wait until no check of a channel waits or runs any more. */
async function checked(app: FreshApp, channelId: string): Promise<void> {
  const deadline = Date.now() + 30_000
  for (;;) {
    const channel = (await app.api(`/channels/${channelId}`)) as { status: string }
    if (channel.status !== 'checking') {
      return
    }
    if (Date.now() > deadline) {
      throw new Error(`${channelId} was still being checked after 30 s`)
    }
    await new Promise((resolve) => setTimeout(resolve, 50))
  }
}

/** Ask for a check through the API and wait until it ended. */
async function check(app: FreshApp, channelId: string, kind: 'quick' | 'full'): Promise<void> {
  await app.send('POST', `/channels/${channelId}/check`, { kind })
  await checked(app, channelId)
}

/** Wait until every picture that is on the screen has arrived. */
async function picturesLoaded(page: Page): Promise<void> {
  await expect
    .poll(() =>
      page.evaluate(() =>
        [...document.querySelectorAll('img')]
          .filter((image) => image.getBoundingClientRect().top < window.innerHeight)
          .every((image) => image.complete && image.naturalWidth > 0),
      ),
    )
    .toBe(true)
}

test('R-CH-01, R-CH-03, R-CH-05, R-CH-10: a channel is added from the welcome screen and its videos are listed', async ({
  page,
  freshApp,
}) => {
  await openApp(page, freshApp)

  await page.getByRole('textbox', { name: 'Channel link or handle' }).fill('@samplechannelone')
  await page.getByRole('main').getByRole('button', { name: 'Add channel' }).click()

  await expect(dialog(page).locator('[data-preview]')).toContainText('Sample Channel One')
  await expect(dialog(page).locator('[data-facts]')).toHaveText('@samplechannelone · 12 videos')
  await expect(dialog(page).locator('[data-folder]')).toHaveText(
    join(freshApp.libraryDir, 'Sample Channel One'),
  )
  await dialog(page).getByRole('button', { name: 'Add channel' }).click()

  await expect(page.getByRole('heading', { level: 1, name: 'Sample Channel One' })).toBeVisible()
  await expect(rows(page)).toHaveCount(12)
  await expect(rows(page).first()).toContainText('Building a cabin in the woods, part 12')
  await expect(rows(page).first()).toContainText('24:18')
  await expect(rows(page).first()).toContainText('48K views')
  await expect(rows(page).first()).toContainText('Not downloaded')
  await expect(page.locator('[data-totals]')).toContainText('12 videos')
  await expect(sidebar(page).locator('[data-status]')).toHaveText('Up to date · checked just now')
  await expect(rows(page).getByText('New', { exact: true })).toHaveCount(0)
})

test('R-FI-01: adding a channel creates its folder in the library', async ({ page, freshApp }) => {
  await openApp(page, freshApp)
  await addChannel(freshApp, '@samplechannelone', SMALL_ID)

  expect(existsSync(join(freshApp.libraryDir, 'Sample Channel One'))).toBe(true)
})

test('R-UI-02: the app opens on the channel that was open last', async ({ page, freshApp }) => {
  await openApp(page, freshApp)
  await addChannel(freshApp, '@samplechannelone', SMALL_ID)
  await addChannel(freshApp, '@samplechannelchanging', CHANGING_ID)
  await page.reload()
  await sidebar(page)
    .getByRole('button', { name: /Sample Channel Changing/ })
    .click()
  await expect(
    page.getByRole('heading', { level: 1, name: 'Sample Channel Changing' }),
  ).toBeVisible()

  await freshApp.restart()
  await page.goto(freshApp.firstUrl)

  await expect(
    page.getByRole('heading', { level: 1, name: 'Sample Channel Changing' }),
  ).toBeVisible()
  await expect(rows(page)).toHaveCount(45)
})

test('R-CH-02: a video link is rejected with a message that says what is accepted', async ({
  page,
  freshApp,
}) => {
  await openApp(page, freshApp)

  await sidebar(page).getByRole('button', { name: 'Add channel' }).click()
  await dialog(page).getByRole('textbox').fill('https://www.youtube.com/watch?v=dQw4w9WgXcQ')
  await dialog(page).getByRole('button', { name: 'Continue' }).click()

  await expect(dialog(page).getByRole('alert')).toContainText('This is a video, not a channel.')
  await expect(dialog(page).getByRole('alert')).toContainText('or a channel ID')
})

test('R-CH-04: adding a channel that exists opens the existing channel and says so', async ({
  page,
  freshApp,
}) => {
  await openApp(page, freshApp)
  await addChannel(freshApp, '@samplechannelone', SMALL_ID)
  await addChannel(freshApp, '@samplechannelchanging', CHANGING_ID)
  await page.reload()
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()

  await sidebar(page).getByRole('button', { name: 'Add channel' }).click()
  await dialog(page)
    .getByRole('textbox')
    .fill('https://www.youtube.com/@SampleChannelChanging/videos')
  await dialog(page).getByRole('button', { name: 'Continue' }).click()

  await expect(
    page.getByRole('heading', { level: 1, name: 'Sample Channel Changing' }),
  ).toBeVisible()
  await expect(dialog(page)).toHaveCount(0)
  await expect(page.locator('[data-banner="existing"]')).toContainText(
    'Sample Channel Changing was added before. Here it is.',
  )
  await expect(sidebar(page).locator('[data-status]')).toHaveCount(2)
})

test('R-CH-03, R-CH-10: a channel whose count YouTube does not give is added all the same, with its titles as they are', async ({
  page,
  freshApp,
}) => {
  await openApp(page, freshApp)

  await sidebar(page).getByRole('button', { name: 'Add channel' }).click()
  await dialog(page).getByRole('textbox').fill('@trickytitles')
  await dialog(page).getByRole('button', { name: 'Continue' }).click()
  await expect(dialog(page).getByText('Found')).toBeVisible()
  await expect(dialog(page).locator('[data-facts]')).toHaveText('@trickytitles')
  await expect(dialog(page).getByText('All videos now, and new ones as they appear.')).toBeVisible()
  await dialog(page).getByRole('button', { name: 'Add channel' }).click()

  await expect(rows(page)).not.toHaveCount(0)
  const shown = await rows(page).locator('[data-title]').allTextContents()
  const listed = (
    (await freshApp.api('/channels/UCtrickytitles0000000002/videos')) as {
      videos: { title: string }[]
    }
  ).videos.map((video) => video.title)
  expect(shown).toEqual(listed)
  expect(shown.some((title) => title.includes('/'))).toBe(true)
})

test('R-CH-11: the first listing of a channel with 5,000 videos ends with all of them, and the app stays usable', async ({
  page,
  freshApp,
}) => {
  await openApp(page, freshApp)

  await sidebar(page).getByRole('button', { name: 'Add channel' }).click()
  await dialog(page).getByRole('textbox').fill('@samplechannellarge')
  await dialog(page).getByRole('button', { name: 'Continue' }).click()
  await dialog(page).getByRole('button', { name: 'Add channel' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Sample Channel Large' })).toBeVisible()
  await sidebar(page).getByRole('button', { name: 'Add channel' }).click()
  await expect(dialog(page).getByRole('textbox')).toBeFocused()
  await dialog(page).getByRole('button', { name: 'Cancel' }).click()

  await expect(page.locator('[data-totals]')).toContainText('5,000 videos', { timeout: 60_000 })
  await expect(rows(page)).toHaveCount(5000, { timeout: 60_000 })
})

test('R-CH-12, R-CH-15, R-CH-23: "Check now" finds the new videos near the top and marks them as new', async ({
  page,
  freshApp,
}) => {
  await openApp(page, freshApp)
  await addChannel(freshApp, '@samplechannelchanging', CHANGING_ID)
  await page.reload()
  await expect(rows(page)).toHaveCount(45)

  await page.getByRole('button', { name: 'Check now' }).click()

  await expect(rows(page)).toHaveCount(47)
  await expect(rows(page).first()).toContainText('A brand new episode')
  await expect(rows(page).first().getByText('New', { exact: true })).toBeVisible()
  await expect(row(page, 'chgnew00002').getByText('New', { exact: true })).toBeVisible()
  await expect(row(page, 'chgnew00003')).toHaveCount(0)
  await expect(sidebar(page).locator('[data-status]')).toHaveText('2 new videos')
  await expect(sidebar(page).getByText('2 new', { exact: true })).toBeVisible()
  await expect(page.locator('[data-check]')).toContainText('Checked just now, 2 new videos')
})

test('R-CH-12, R-CH-13, R-CH-14: only full checks find what changed far down, and the second one marks a missing video as removed', async ({
  page,
  freshApp,
}) => {
  await openApp(page, freshApp)
  await addChannel(freshApp, '@samplechannelchanging', CHANGING_ID)
  await check(freshApp, CHANGING_ID, 'quick')
  await page.reload()
  await expect(rows(page)).toHaveCount(47)

  await page.getByRole('button', { name: 'More actions' }).click()
  await page.getByRole('menuitem', { name: 'Full check' }).click()

  await expect(rows(page)).toHaveCount(48)
  await expect(row(page, 'chgnew00003')).toContainText('A late upload far down the channel')
  await expect(row(page, 'chg00000044')).toContainText('Episode 44, now with a better title')
  await expect(row(page, 'chg00000003')).toContainText('Episode 3, renamed far down the channel')
  await expect(row(page, 'chg00000042')).not.toContainText('Removed from YouTube')

  await check(freshApp, CHANGING_ID, 'quick')
  await expect(row(page, 'chg00000042')).not.toContainText('Removed from YouTube')
  await page.getByRole('button', { name: 'More actions' }).click()
  await page.getByRole('menuitem', { name: 'Full check' }).click()

  await expect(row(page, 'chg00000042')).toContainText('Removed from YouTube')
  await expect(rows(page)).toHaveCount(48)
})

test('R-CH-25, R-CH-13: a failed check shows a banner, keeps the list, and "Try again" recovers', async ({
  page,
  freshApp,
}) => {
  await openApp(page, freshApp)
  await addChannel(freshApp, '@samplechannelchanging', CHANGING_ID)
  await check(freshApp, CHANGING_ID, 'quick')
  await check(freshApp, CHANGING_ID, 'full')
  await check(freshApp, CHANGING_ID, 'full')
  await check(freshApp, CHANGING_ID, 'quick')
  await page.reload()
  await expect(row(page, 'chg00000042')).toContainText('Removed from YouTube')

  await page.getByRole('button', { name: 'Check now' }).click()

  const banner = page.locator('[data-banner="check-failed"]')
  await expect(banner).toContainText('Could not reach YouTube')
  await expect(banner).toContainText('The video list below is from the last successful check')
  await expect(sidebar(page).locator('[data-status]')).toHaveText('Could not check')
  await expect(rows(page)).toHaveCount(48)
  await expect(row(page, 'chg00000042')).toContainText('Removed from YouTube')

  await banner.getByRole('button', { name: 'Try again' }).click()

  await expect(banner).toHaveCount(0)
  await expect(row(page, 'chg00000042')).not.toContainText('Removed from YouTube')
  await expect(sidebar(page).locator('[data-status]')).not.toHaveText('Could not check')
})

test('R-CH-31, R-CH-32: a channel is paused, resumed and removed from its menu, and its folder stays', async ({
  page,
  freshApp,
}) => {
  await openApp(page, freshApp)
  await addChannel(freshApp, '@samplechannelone', SMALL_ID)
  await page.reload()
  await expect(rows(page)).toHaveCount(12)

  await sidebar(page)
    .getByRole('button', { name: /Sample Channel One/ })
    .click({ button: 'right' })
  await page.getByRole('menuitem', { name: 'Pause channel' }).click()
  await expect(sidebar(page).locator('[data-status]')).toHaveText('Paused')
  await expect(page.getByRole('button', { name: 'Check now' })).toHaveCount(0)
  await expect(page.locator('[data-check]')).toContainText('Paused. No checks until you resume.')

  await page.getByRole('button', { name: 'More actions' }).click()
  await page.getByRole('menuitem', { name: 'Resume channel' }).click()
  await expect(page.getByRole('button', { name: 'Check now' })).toBeVisible()

  await page.getByRole('button', { name: 'More actions' }).click()
  await page.getByRole('menuitem', { name: 'Remove channel' }).click()
  await expect(dialog(page)).toContainText(join(freshApp.libraryDir, 'Sample Channel One'))
  await dialog(page).getByRole('button', { name: 'Remove channel' }).click()

  await expect(page.getByRole('heading', { name: 'Mirror your first channel' })).toBeVisible()
  await expect(sidebar(page).locator('[data-status]')).toHaveCount(0)
  expect(existsSync(join(freshApp.libraryDir, 'Sample Channel One'))).toBe(true)
  expect(((await freshApp.api('/state')) as { channels: unknown[] }).channels).toEqual([])
})

test('R-UI-13: the channel menu and the dialogs work with the keyboard alone', async ({
  page,
  freshApp,
}) => {
  await openApp(page, freshApp)
  await addChannel(freshApp, '@samplechannelone', SMALL_ID)
  await page.reload()
  await expect(rows(page)).toHaveCount(12)

  await page.getByRole('button', { name: 'More actions' }).focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('menuitem', { name: 'Check now' })).toBeFocused()
  await page.keyboard.press('End')
  await expect(page.getByRole('menuitem', { name: 'Remove channel' })).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(dialog(page)).toBeVisible()
  await page.keyboard.press('Escape')

  await expect(dialog(page)).toHaveCount(0)
  await expect(page.getByRole('heading', { level: 1, name: 'Sample Channel One' })).toBeVisible()
})

for (const theme of ['light', 'dark'] as const) {
  test.describe(`in the ${theme} theme`, () => {
    test.use({ colorScheme: theme })

    test(`R-TH-09, R-UI-14: the add channel dialog looks as recorded and is accessible in the ${theme} theme`, async ({
      page,
      freshApp,
    }) => {
      await openApp(page, freshApp)
      await addChannel(freshApp, '@samplechannelone', SMALL_ID)
      await page.reload()
      await expect(rows(page)).toHaveCount(12)
      await picturesLoaded(page)
      await sidebar(page).getByRole('button', { name: 'Add channel' }).click()
      await expect(dialog(page).getByRole('textbox')).toBeFocused()
      await expect(page).toHaveScreenshot(`add-channel-1-${theme}.png`, {
        mask: [page.locator('[data-free-space]')],
      })
      const first = await new AxeBuilder({ page }).analyze()

      await dialog(page).getByRole('textbox').fill('@samplechannelchanging')
      await dialog(page).getByRole('button', { name: 'Continue' }).click()
      await expect(dialog(page).locator('[data-facts]')).toHaveText(
        '@samplechannelchanging · 57 videos',
      )
      await picturesLoaded(page)

      await expect(page).toHaveScreenshot(`add-channel-2-${theme}.png`, {
        // The place of the library differs from machine to machine.
        mask: [page.locator('[data-free-space]'), dialog(page).locator('[data-folder]')],
      })
      const second = await new AxeBuilder({ page }).analyze()
      expect(first.violations.map((violation) => violation.id)).toEqual([])
      expect(second.violations.map((violation) => violation.id)).toEqual([])
    })

    test(`R-TH-09, R-UI-14: the channel page looks as recorded and is accessible in the ${theme} theme`, async ({
      page,
      freshApp,
    }) => {
      await openApp(page, freshApp)
      await addChannel(freshApp, '@samplechannelone', SMALL_ID)
      await addChannel(freshApp, '@samplechannelchanging', CHANGING_ID)
      await check(freshApp, CHANGING_ID, 'quick')
      await page.reload()
      await sidebar(page)
        .getByRole('button', { name: /Sample Channel Changing/ })
        .click()
      await expect(rows(page)).toHaveCount(47)
      await picturesLoaded(page)
      await page.evaluate(() => document.fonts.ready)

      await expect(page).toHaveScreenshot(`channel-${theme}.png`, {
        mask: [page.locator('[data-free-space]')],
      })
      const results = await new AxeBuilder({ page }).analyze()
      expect(results.violations.map((violation) => violation.id)).toEqual([])
    })

    test(`R-TH-09, R-UI-14: the channel menu and the remove dialog look as recorded and are accessible in the ${theme} theme`, async ({
      page,
      freshApp,
    }) => {
      await openApp(page, freshApp)
      await addChannel(freshApp, '@samplechannelone', SMALL_ID)
      await page.reload()
      await expect(rows(page)).toHaveCount(12)
      await picturesLoaded(page)
      await page.evaluate(() => document.fonts.ready)

      await page.getByRole('button', { name: 'More actions' }).click()
      await expect(page.getByRole('menu')).toBeVisible()
      await expect(page).toHaveScreenshot(`channel-menu-${theme}.png`, {
        mask: [page.locator('[data-free-space]')],
      })
      const menu = await new AxeBuilder({ page }).analyze()
      await page.getByRole('menuitem', { name: 'Remove channel' }).click()
      await expect(dialog(page)).toBeVisible()
      await expect(page).toHaveScreenshot(`remove-channel-${theme}.png`, {
        mask: [page.locator('[data-free-space]'), dialog(page).locator('[data-folder]')],
      })
      const removing = await new AxeBuilder({ page }).analyze()

      expect(menu.violations.map((violation) => violation.id)).toEqual([])
      expect(removing.violations.map((violation) => violation.id)).toEqual([])
    })

    test(`R-TH-09, R-UI-14: a failed check looks as recorded and is accessible in the ${theme} theme`, async ({
      page,
      freshApp,
    }) => {
      await openApp(page, freshApp)
      await addChannel(freshApp, '@samplechannelchanging', CHANGING_ID)
      for (const kind of ['quick', 'full', 'full', 'quick', 'quick'] as const) {
        await check(freshApp, CHANGING_ID, kind)
      }
      await page.reload()
      await expect(page.locator('[data-banner="check-failed"]')).toBeVisible()
      await expect(rows(page)).toHaveCount(48)
      await picturesLoaded(page)
      await page.evaluate(() => document.fonts.ready)

      await expect(page).toHaveScreenshot(`check-failed-${theme}.png`, {
        // The time of the last successful check is the time of this test run.
        mask: [
          page.locator('[data-free-space]'),
          page.locator('[data-banner="check-failed"] p').nth(1),
        ],
      })
      const results = await new AxeBuilder({ page }).analyze()
      expect(results.violations.map((violation) => violation.id)).toEqual([])
    })
  })
}
