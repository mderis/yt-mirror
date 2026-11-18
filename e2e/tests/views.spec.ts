import AxeBuilder from '@axe-core/playwright'
import type { Locator, Page } from '@playwright/test'

import { expect, test, type FreshApp } from './fresh-app'

/**
 * List and grid, the downloads panel and the keyboard (docs/TESTING.md
 * section 6, flow 13): the views and the panel in both themes, as recorded and
 * accessible, and the main flow with the keyboard alone. Every test starts an
 * app of its own.
 */
test.describe.configure({ mode: 'default' })

const SMALL_ID = 'UCsmallchannel0000000001'
const FIRST = 'small000012'
const SECOND = 'small000011'
const THIRD = 'small000008'

const row = (page: Page, videoId: string): Locator => page.locator(`[data-video="${videoId}"]`)

async function openChannel(page: Page, app: FreshApp): Promise<void> {
  await app.finishSetup()
  await app.send('POST', '/channels/lookup', { text: '@samplechannelone' })
  await app.send('POST', '/channels', { channel_id: SMALL_ID, auto_mirror: false })
  await expect
    .poll(async () => ((await app.api(`/channels/${SMALL_ID}`)) as { status: string }).status)
    .not.toBe('checking')
  await page.goto(app.firstUrl)
  await expect(row(page, FIRST)).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
}

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

async function accessible(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page }).analyze()
  expect(results.violations.map((violation) => violation.id)).toEqual([])
}

test('R-UI-13, R-MI-01, R-UI-03: the main flow works with the keyboard alone', async ({
  page,
  freshApp,
}) => {
  await openChannel(page, freshApp)
  await page.locator('body').click({ position: { x: 1, y: 1 } })

  await page.keyboard.press('ArrowDown')
  await expect(row(page, FIRST)).toHaveAttribute('data-current', 'true')
  await page.keyboard.press('ArrowDown')
  await page.keyboard.press('Space')
  await expect(page.getByRole('region', { name: 'Selected videos' })).toContainText('1 selected')
  await page.keyboard.press('m')
  await expect(row(page, SECOND).getByText('Synced · 270p')).toBeVisible({ timeout: 20_000 })

  await page.keyboard.press('Escape')
  await page.keyboard.press('g')
  await expect(page.locator('[data-view="grid"]')).toBeVisible()
  await page.keyboard.press('/')
  await expect(page.getByRole('searchbox', { name: 'Filter by title' })).toBeFocused()
  await page.keyboard.type('cabin')
  await expect(page.locator('[data-video]')).toHaveCount(1)
  await page.keyboard.press('Escape')
  await page.locator('body').click({ position: { x: 1, y: 1 } })
  await page.keyboard.press('?')
  await expect(page.getByRole('dialog', { name: 'Keyboard shortcuts' })).toBeVisible()
})

for (const theme of ['light', 'dark'] as const) {
  test.describe(`in the ${theme} theme`, () => {
    test.use({ colorScheme: theme })

    test(`R-TH-09, R-UI-03, R-UI-14: the grid looks as recorded and is accessible in the ${theme} theme`, async ({
      page,
      freshApp,
    }) => {
      await openChannel(page, freshApp)

      await page.getByRole('button', { name: 'Grid view' }).click()
      await expect(page.locator('[data-view="grid"]')).toBeVisible()
      await picturesLoaded(page)

      await expect(page).toHaveScreenshot(`grid-${theme}.png`, {
        mask: [page.locator('[data-free-space]')],
      })
      await accessible(page)
    })

    test(`R-TH-09, R-QU-02, R-UI-14: the downloads panel looks as recorded and is accessible in the ${theme} theme`, async ({
      page,
      freshApp,
    }) => {
      await openChannel(page, freshApp)
      await freshApp.send('POST', '/queue/pause')
      await freshApp.send('POST', '/videos/mirror', { ids: [FIRST, SECOND, THIRD] })
      await page.reload()
      await page
        .getByRole('region', { name: 'Downloads' })
        .getByRole('button', { name: 'Show queue' })
        .click()
      const panel = page.getByRole('complementary', { name: 'Downloads' })
      await expect(panel.locator('[data-waiting] li')).toHaveCount(3)
      await picturesLoaded(page)

      await expect(page).toHaveScreenshot(`downloads-panel-${theme}.png`, {
        mask: [page.locator('[data-free-space]'), panel.locator('[data-queue-line]')],
      })
      await accessible(page)
    })

    test(`R-TH-09, R-UI-13, R-UI-14: the list of shortcuts looks as recorded and is accessible in the ${theme} theme`, async ({
      page,
      freshApp,
    }) => {
      await openChannel(page, freshApp)
      await picturesLoaded(page)

      await page.locator('body').click({ position: { x: 1, y: 1 } })
      await page.keyboard.press('?')
      await expect(page.getByRole('dialog', { name: 'Keyboard shortcuts' })).toBeVisible()

      await expect(page).toHaveScreenshot(`shortcuts-${theme}.png`, {
        mask: [page.locator('[data-free-space]')],
      })
      await accessible(page)
    })
  })
}
