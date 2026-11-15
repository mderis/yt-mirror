import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

import AxeBuilder from '@axe-core/playwright'
import type { Locator, Page } from '@playwright/test'

import { expect, test, type FreshApp } from './fresh-app'

/**
 * Downloads, end to end (docs/TESTING.md section 6, flow 2): mirror two
 * videos, watch their progress, see them synced, open the details. The fake
 * YouTube writes real video files with the real ffmpeg.
 */
test.describe.configure({ mode: 'serial' })

const SMALL_ID = 'UCsmallchannel0000000001'
const FIRST = 'small000012'
const SECOND = 'small000011'
const FIRST_TITLE = 'Building a cabin in the woods, part 12'
const SECOND_TITLE = 'Q and A, your questions answered'

const sidebar = (page: Page): Locator => page.getByRole('navigation', { name: 'Channels' })
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

test('R-MI-01, R-QU-04, R-FB-01, R-FB-02, R-UI-08: two videos are mirrored one after another, with progress, and synced', async ({
  page,
  freshApp,
}) => {
  await openChannel(page, freshApp)

  await row(page, FIRST).getByRole('button', { name: 'Mirror' }).click()
  await row(page, SECOND).getByRole('button', { name: 'Mirror' }).click()

  await expect(row(page, SECOND).getByText('Queued')).toBeVisible()
  await expect(row(page, FIRST).getByText(/Downloading \d+%/)).toBeVisible()
  await expect(row(page, FIRST).getByRole('progressbar')).toBeVisible()
  await expect(sidebar(page).getByText(/Mirroring 1 of 2/)).toBeVisible()
  await expect(row(page, FIRST).getByText('Synced · 270p')).toBeVisible({ timeout: 20_000 })
  await expect(row(page, SECOND).getByText('Synced · 270p')).toBeVisible({ timeout: 20_000 })
  await expect(row(page, FIRST).getByRole('button', { name: 'Play' })).toBeVisible()
  await expect(row(page, FIRST).getByRole('button', { name: 'Show in Finder' })).toBeVisible()

  const folder = join(freshApp.libraryDir, 'Sample Channel One')
  expect(readdirSync(folder).sort()).toEqual(
    ['.yt-mirror', `${FIRST_TITLE}.mkv`, `${SECOND_TITLE}.mkv`].sort(),
  )
  const file = statSync(join(folder, `${FIRST_TITLE}.mkv`))
  const published = Date.parse('2026-11-13T18:00:00Z')
  expect(file.mtimeMs).toBe(published)
  expect(file.birthtimeMs).toBe(published)

  await row(page, FIRST)
    .getByRole('button', { name: `Details of ${FIRST_TITLE}` })
    .click()
  const panel = page.getByRole('complementary', { name: 'Video details' })
  await expect(panel.getByRole('heading', { name: FIRST_TITLE })).toBeVisible()
  await expect(panel.locator('[data-fact="name"]')).toContainText(`${FIRST_TITLE}.mkv`)
  await expect(panel.locator('[data-fact="uploaded"]')).toContainText('(also set as the file date)')
  await expect(panel.locator('[data-details-chapters]')).toContainText('The middle')
  await page.keyboard.press('Escape')
  await expect(panel).toHaveCount(0)
})

test('R-QU-02: a download that is cancelled leaves nothing, and Mirror works again', async ({
  page,
  freshApp,
}) => {
  await openChannel(page, freshApp)

  await row(page, FIRST).getByRole('button', { name: 'Mirror' }).click()
  await expect(row(page, FIRST).getByText(/Downloading/)).toBeVisible()
  await row(page, FIRST)
    .getByRole('button', { name: `Cancel the download of ${FIRST_TITLE}` })
    .click()

  await expect(row(page, FIRST).getByText('Not downloaded')).toBeVisible()
  const folder = join(freshApp.libraryDir, 'Sample Channel One')
  expect(readdirSync(folder).filter((name) => !name.startsWith('.'))).toEqual([])
  expect(readdirSync(join(folder, '.yt-mirror', 'tmp'))).toEqual([])
  await row(page, FIRST).getByRole('button', { name: 'Mirror' }).click()
  await expect(row(page, FIRST).getByText('Synced · 270p')).toBeVisible({ timeout: 20_000 })
})

test('R-CH-32: "Delete the files" moves the files of a channel to the Trash and keeps a file of the user', async ({
  page,
  freshApp,
}) => {
  await openChannel(page, freshApp)
  await row(page, FIRST).getByRole('button', { name: 'Mirror' }).click()
  await expect(row(page, FIRST).getByText('Synced · 270p')).toBeVisible({ timeout: 20_000 })
  const folder = join(freshApp.libraryDir, 'Sample Channel One')
  writeFileSync(join(folder, 'my notes.txt'), 'the user wrote this')

  await page.getByRole('button', { name: 'More actions' }).click()
  await page.getByRole('menuitem', { name: 'Remove channel' }).click()
  const dialog = page.getByRole('dialog', { name: 'Remove Sample Channel One?' })
  await expect(dialog).toContainText('1 downloaded video')
  await dialog.getByRole('radio', { name: /Delete the files/ }).check()
  await expect(dialog).toContainText('1 file')
  await expect(dialog).toContainText('Other files in the folder stay where they are.')
  await dialog.getByRole('button', { name: 'Remove channel' }).click()

  await expect(dialog).toHaveCount(0)
  await expect
    .poll(() => readdirSync(freshApp.trashDir).sort())
    .toEqual(
      [
        '.yt-mirror',
        'channel.json',
        `${FIRST}.info.json`,
        `${FIRST}.jpg`,
        `${FIRST_TITLE}.mkv`,
      ].sort(),
    )
  expect(readdirSync(folder)).toEqual(['my notes.txt'])
  expect(readFileSync(join(folder, 'my notes.txt'), 'utf8')).toBe('the user wrote this')
})

for (const theme of ['light', 'dark'] as const) {
  test(`R-UI-14, R-TH-01: the rows of every download state and the details panel, in the ${theme} theme`, async ({
    page,
    freshApp,
  }) => {
    await page.emulateMedia({ colorScheme: theme })
    await openChannel(page, freshApp)
    await row(page, FIRST).getByRole('button', { name: 'Mirror' }).click()
    await expect(row(page, FIRST).getByText('Synced · 270p')).toBeVisible({ timeout: 20_000 })
    await row(page, FIRST)
      .getByRole('button', { name: `Details of ${FIRST_TITLE}` })
      .click()
    await expect(page.locator('[data-details-file]')).toBeVisible()

    const scan = await new AxeBuilder({ page }).analyze()
    expect(
      scan.violations.filter((found) => ['serious', 'critical'].includes(found.impact ?? '')),
    ).toEqual([])
  })
}
