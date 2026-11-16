import { existsSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

import AxeBuilder from '@axe-core/playwright'
import type { Locator, Page } from '@playwright/test'

import { expect, test, type FreshApp } from './fresh-app'

/**
 * Downloads, end to end (docs/TESTING.md section 6, flow 2): mirror two
 * videos, watch their progress, see them synced, open the details. The fake
 * YouTube writes real video files with the real ffmpeg.
 */
// One test after another in one worker, as each starts an app of its own. Not 'serial':
// a failed test must never keep the next ones, and their screenshots, from running.
test.describe.configure({ mode: 'default' })

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

test('R-QU-02: a cancel while YouTube is only asked ends within half a second, and Mirror works again', async ({
  page,
  freshApp,
}) => {
  // The fake YouTube answers the metadata lookup of this video after 3 s, as yt-dlp's can.
  const SLOW = 'small000010'
  await openChannel(page, freshApp)
  await row(page, SLOW).getByRole('button', { name: 'Mirror' }).click()
  await expect(row(page, SLOW).getByText('Downloading')).toBeVisible()

  const pressed = Date.now()
  await row(page, SLOW)
    .getByRole('button', { name: 'Cancel the download of Restoring an old workbench' })
    .click()
  await expect(row(page, SLOW).getByText('Not downloaded')).toBeVisible({ timeout: 500 })
  expect(Date.now() - pressed).toBeLessThan(500)

  const folder = join(freshApp.libraryDir, 'Sample Channel One')
  const temp = join(folder, '.yt-mirror', 'tmp')
  expect(readdirSync(folder).filter((name) => !name.startsWith('.'))).toEqual([])
  expect(existsSync(temp) ? readdirSync(temp) : []).toEqual([])
  await row(page, SLOW).getByRole('button', { name: 'Mirror' }).click()
  await expect(row(page, SLOW).getByText('Synced · 270p')).toBeVisible({ timeout: 20_000 })
})

test('R-QU-04: the percent and the bar of a row grow as the fake YouTube sends progress in steps', async ({
  page,
  freshApp,
}) => {
  await openChannel(page, freshApp)
  // Notes every text of the chip and every width of the bar the row shows.
  await page.evaluate((videoId) => {
    const seen: { chip: string; width: string; working: boolean }[] = []
    ;(window as unknown as { seen: typeof seen }).seen = seen
    const target = document.querySelector(`[data-video="${videoId}"]`)
    if (target === null) throw new Error('no row')
    const note = (): void => {
      const chip = target.querySelector('[data-chips]')?.textContent?.trim() ?? ''
      const fill = target.querySelector('[role="progressbar"]')
        ?.firstElementChild as HTMLElement | null
      const entry = {
        chip,
        width: fill?.style.width ?? '',
        working: fill?.hasAttribute('data-working') ?? false,
      }
      const last = seen.at(-1)
      if (!last || last.chip !== entry.chip || last.width !== entry.width) seen.push(entry)
    }
    new MutationObserver(note).observe(target, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
    })
  }, FIRST)

  await row(page, FIRST).getByRole('button', { name: 'Mirror' }).click()
  await expect(row(page, FIRST).getByText('Synced · 270p')).toBeVisible({ timeout: 20_000 })

  const seen = await page.evaluate(
    () => (window as unknown as { seen: { chip: string; width: string; working: boolean }[] }).seen,
  )
  const percents = seen
    .map((entry) => /Downloading (\d+)%/.exec(entry.chip)?.[1])
    .filter((value): value is string => value !== undefined)
    .map(Number)
  const widths = seen
    .filter((entry) => /Downloading \d+%/.test(entry.chip))
    .map((entry) => Number.parseFloat(entry.width))
  expect(new Set(percents).size).toBeGreaterThanOrEqual(3)
  expect(percents).toEqual([...percents].sort((a, b) => a - b))
  expect(Math.max(...percents)).toBeGreaterThanOrEqual(75)
  expect(widths).toEqual([...widths].sort((a, b) => a - b))
  expect(widths).toEqual(percents)
  const processing = seen.filter((entry) => entry.chip.startsWith('Processing'))
  expect(processing.length).toBeGreaterThan(0)
  expect(processing.every((entry) => entry.working && !/%/.test(entry.chip))).toBe(true)
  const firstProcessing = seen.findIndex((entry) => entry.chip.startsWith('Processing'))
  const lastDownloading = seen.findLastIndex((entry) => /Downloading \d+%/.test(entry.chip))
  expect(firstProcessing).toBeGreaterThan(lastDownloading)
})

test('R-CH-32, R-QA-06: removing a channel while its video downloads leaves no file and no folder', async ({
  page,
  freshApp,
}) => {
  await openChannel(page, freshApp)
  const folder = join(freshApp.libraryDir, 'Sample Channel One')

  await row(page, FIRST).getByRole('button', { name: 'Mirror' }).click()
  await expect(row(page, FIRST).getByText(/Downloading \d+%/)).toBeVisible()
  await page.getByRole('button', { name: 'More actions' }).click()
  await page.getByRole('menuitem', { name: 'Remove channel' }).click()
  const dialog = page.getByRole('dialog', { name: 'Remove Sample Channel One?' })
  await dialog.getByRole('radio', { name: /Delete the files/ }).check()
  await dialog.getByRole('button', { name: 'Remove channel' }).click()

  await expect(sidebar(page).getByRole('button', { name: /Sample Channel One/ })).toHaveCount(0)
  await expect.poll(() => existsSync(folder)).toBe(false)
  // The download that was stopped must not write anything into the folder afterwards.
  await page.waitForTimeout(1500)
  expect(existsSync(folder)).toBe(false)
  expect(((await freshApp.api('/state')) as { channels: unknown[] }).channels).toEqual([])
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
