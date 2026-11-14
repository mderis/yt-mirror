import { rmSync } from 'node:fs'
import { join } from 'node:path'

import AxeBuilder from '@axe-core/playwright'
import type { Page } from '@playwright/test'

import { expect, test, type FreshApp } from './fresh-app'

/**
 * The first run and the tools (docs/TESTING.md section 6, flow 1). Every test
 * starts an app of its own on empty folders. The tools are small stand-ins.
 */
test.describe.configure({ mode: 'serial' })

const row = (page: Page, tool: string) => page.locator(`[data-tool="${tool}"]`)

async function openFirstRun(page: Page, app: FreshApp): Promise<void> {
  await page.goto(app.firstUrl)
  await expect(
    page.getByRole('heading', { level: 1, name: 'Getting yt-mirror ready' }),
  ).toBeVisible()
}

async function finishFirstRun(page: Page, app: FreshApp): Promise<void> {
  await openFirstRun(page, app)
  await page.getByRole('button', { name: 'Continue' }).click()
  await expect(page.getByText('yt-mirror is running.')).toBeVisible()
}

test('R-IN-03: the first run shows the tools, installs the missing ones, then the app opens', async ({
  page,
  freshApp,
}) => {
  await openFirstRun(page, freshApp)

  await expect(page.locator('[data-tool]')).toHaveCount(4)
  await expect(row(page, 'python')).toContainText('Python environment')
  await expect(row(page, 'ytdlp')).toContainText('The YouTube download engine')
  await expect(row(page, 'ffmpeg')).toContainText('Installed')
  await expect(row(page, 'deno')).toContainText('Installed')
  await expect(page.getByText('About 120 MB in total. This only happens once.')).toBeVisible()
  await page.getByRole('button', { name: 'Continue' }).click()

  await expect(page.getByText('yt-mirror is running.')).toBeVisible()
  await expect(page.locator('[data-banner]')).toHaveCount(0)
  const state = (await freshApp.api('/tools')) as {
    setup_required: boolean
    tools: { name: string; source: string | null }[]
  }
  expect(state.setup_required).toBe(false)
  expect(state.tools.find((tool) => tool.name === 'ffmpeg')?.source).toBe('first-source')
})

test('R-IN-03: once the first run is done, it does not come back', async ({ page, freshApp }) => {
  await finishFirstRun(page, freshApp)

  await freshApp.restart()
  await page.goto(freshApp.firstUrl)

  await expect(page.getByText('yt-mirror is running.')).toBeVisible()
  await expect(page.getByText('Getting yt-mirror ready')).toHaveCount(0)
})

test('R-IN-03: a tool whose first source fails comes from the second source', async ({
  page,
  freshApp,
}) => {
  await freshApp.failDownload('ffmpeg.zip')

  await openFirstRun(page, freshApp)

  await expect(row(page, 'ffmpeg')).toContainText('Installed')
  const state = (await freshApp.api('/tools')) as { tools: { name: string; source: string }[] }
  expect(state.tools.find((tool) => tool.name === 'ffmpeg')?.source).toBe('second-source')
})

test('R-IN-03: a failed step says why, the other tools go on, and "Try again" repairs it', async ({
  page,
  freshApp,
}) => {
  await freshApp.failDownload('ffmpeg.zip')
  await freshApp.failDownload('both.tar.xz')

  await openFirstRun(page, freshApp)

  await expect(row(page, 'ffmpeg')).toContainText('Download failed: no internet connection')
  await expect(row(page, 'deno')).toContainText('Installed')
  await expect(page.getByRole('button', { name: 'Continue' })).toBeDisabled()
  await row(page, 'ffmpeg').getByRole('button', { name: 'Try again' }).click()

  await expect(row(page, 'ffmpeg')).toContainText('Installed')
  await expect(page.getByRole('button', { name: 'Continue' })).toBeEnabled()
})

test('R-IN-04: a tool that stopped working gets a banner, and "Install now" repairs it', async ({
  page,
  freshApp,
}) => {
  await finishFirstRun(page, freshApp)
  rmSync(join(freshApp.toolDir, 'deno', 'deno'))

  await freshApp.restart()
  await page.goto(freshApp.firstUrl)

  const banner = page.locator('[data-banner="deno"]')
  await expect(page.getByText('yt-mirror is running.')).toBeVisible()
  await expect(banner).toContainText('Deno no longer works.')
  await banner.getByRole('button', { name: 'Install now' }).click()
  await expect(page.locator('[data-banner]')).toHaveCount(0)
  await expect(page.getByText('Getting yt-mirror ready')).toHaveCount(0)
})

test('R-IN-03: with two tools gone, the first-run screen is shown again', async ({
  page,
  freshApp,
}) => {
  await finishFirstRun(page, freshApp)
  rmSync(join(freshApp.toolDir, 'deno'), { recursive: true })
  rmSync(join(freshApp.toolDir, 'ffmpeg'), { recursive: true })

  await freshApp.restart()
  await openFirstRun(page, freshApp)

  await expect(row(page, 'ffmpeg')).toContainText('Installed')
  await expect(row(page, 'deno')).toContainText('Installed')
})

for (const theme of ['light', 'dark'] as const) {
  test.describe(`with the system set to ${theme}`, () => {
    test.use({ colorScheme: theme })

    test(`R-TH-09, R-UI-14: the first-run screen looks as recorded and is accessible in the ${theme} theme`, async ({
      page,
      freshApp,
    }) => {
      await freshApp.failDownload('ffmpeg.zip')
      await freshApp.failDownload('both.tar.xz')
      await openFirstRun(page, freshApp)
      await expect(row(page, 'ffmpeg')).toContainText('Download failed')
      await expect(row(page, 'deno')).toContainText('Installed')
      await page.evaluate(() => document.fonts.ready)

      await expect(page).toHaveScreenshot(`setup-${theme}.png`)
      const results = await new AxeBuilder({ page }).analyze()
      expect(results.violations.map((violation) => violation.id)).toEqual([])
    })
  })
}
