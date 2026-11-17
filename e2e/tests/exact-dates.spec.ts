import { existsSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'

import type { Locator, Page } from '@playwright/test'

import { expect, test, type FreshApp } from './fresh-app'

/**
 * Exact dates and automatic checks, end to end (milestone M4): exact dates
 * arrive in the list, YouTube's "not a bot" check holds the lookups and the
 * channel waits for YouTube, the optional key fetches the dates through the
 * fake YouTube API, and a new title renames a mirrored file.
 */
test.describe.configure({ mode: 'default' })

const SMALL_ID = 'UCsmallchannel0000000001'
const BOT_ID = 'UCbotcheckdates000000012'
const RENAMING_ID = 'UCrenamingchannel0000013'

const sidebar = (page: Page): Locator => page.getByRole('navigation', { name: 'Channels' })
const dates = (page: Page, state: string): Locator => page.locator(`main [data-date="${state}"]`)

async function added(app: FreshApp, handle: string, channelId: string): Promise<void> {
  await app.send('POST', '/channels/lookup', { text: handle })
  await app.send('POST', '/channels', { channel_id: channelId, auto_mirror: false })
  await expect
    .poll(async () => ((await app.api(`/channels/${channelId}`)) as { status: string }).status)
    .not.toBe('checking')
}

test.describe('with exact dates looked up fast', () => {
  test.use({ lookupsPerHour: 360_000 })

  test('R-DT-05, R-DT-13, R-FB-01: the exact dates arrive in the list, newest first, and the channel is up to date again', async ({
    page,
    freshApp,
  }) => {
    await freshApp.finishSetup()
    await added(freshApp, '@samplechannelone', SMALL_ID)
    await page.goto(freshApp.firstUrl)

    await expect(dates(page, 'exact')).toHaveCount(12, { timeout: 30_000 })
    await expect(dates(page, 'waiting')).toHaveCount(0)
    await expect(page.locator('[data-video="small000012"] [data-date]')).toHaveText(
      'Uploaded 13 Nov 2026',
    )
    await expect(sidebar(page).locator('[data-status]')).toContainText('Up to date')
  })

  test('R-ER-05, R-FB-01, R-DT-12: under the "not a bot" check the channel waits, and the key gets the dates without it', async ({
    page,
    freshApp,
  }) => {
    await freshApp.finishSetup()
    await added(freshApp, '@botcheckdates', BOT_ID)
    await page.goto(freshApp.firstUrl)

    const banner = page.locator('[data-banner="youtube-pause"]')
    await expect(banner).toBeVisible({ timeout: 20_000 })
    await expect(banner).toContainText('The optional API key gets exact dates without this check.')
    await expect(sidebar(page).locator('[data-status]')).toHaveText('Waiting for YouTube')
    await expect(dates(page, 'unavailable')).toHaveCount(3)

    await banner.getByRole('button', { name: 'Set up the API key' }).click()
    const guide = page.locator('[data-dialog="api-key"]')
    await expect(guide).toContainText('The key is free.')
    await guide.getByLabel('Paste it here').fill('fixture-invalid-key')
    await guide.getByRole('button', { name: 'Test key' }).click()
    await expect(guide.locator('[data-key-test]')).toContainText('YouTube did not accept this key.')
    await guide.getByLabel('Paste it here').fill('fixture-good-key-e2e')
    await guide.getByRole('button', { name: 'Test key' }).click()
    await expect(guide.locator('[data-key-test]')).toContainText('Key works.')
    await page.getByRole('button', { name: 'Save key' }).click()

    await expect(guide).toHaveCount(0)
    await expect(dates(page, 'exact')).toHaveCount(3, { timeout: 20_000 })
    await expect(page.locator('[data-video="botdate0001"] [data-date]')).toHaveText(
      'Uploaded 14 Jun 2023',
    )
    const key = (await freshApp.api('/settings/api-key')) as { status: string }
    expect(key.status).toBe('saved')
    expect(JSON.stringify(await freshApp.api('/state'))).not.toContain('fixture-good-key-e2e')
  })
})

test('R-FN-06, R-DT-10: a new title renames the mirrored file at the next check, and its dates stay', async ({
  page,
  freshApp,
}) => {
  await freshApp.finishSetup()
  await added(freshApp, '@renamingchannel', RENAMING_ID)
  await page.goto(freshApp.firstUrl)
  const row = page.locator('[data-video="rename00001"]')
  await row.getByRole('button', { name: 'Mirror' }).click()
  await expect(row.getByText(/Synced/)).toBeVisible({ timeout: 20_000 })
  const folder = join(freshApp.libraryDir, 'Renaming Channel')
  expect(existsSync(join(folder, 'The first title.mkv'))).toBe(true)

  await page.getByRole('button', { name: 'Check now' }).click()

  const renamed = 'A better title： part 2.mkv'
  await expect
    .poll(() => readdirSync(folder).filter((name) => name.endsWith('.mkv')))
    .toEqual([renamed])
  const file = statSync(join(folder, renamed))
  const published = Date.parse('2026-11-11T20:15:00Z')
  expect(file.mtimeMs).toBe(published)
  expect(file.birthtimeMs).toBe(published)
  await expect(row).toContainText('A better title: part 2')
})
