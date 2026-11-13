import { expect, test, type Page } from '@playwright/test'

import { PREVIEW_URL } from '../settings'

/**
 * The theme preview page (R-TH-08) is served by the development server only.
 * Its screenshot shows every token in both themes side by side, so one image
 * per browser covers both themes (R-TH-09).
 */
async function openPreview(page: Page): Promise<void> {
  await page.goto(`${PREVIEW_URL}/theme-preview.html`)
  await expect(page.getByRole('heading', { level: 1, name: 'Theme preview' })).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
}

test.use({ colorScheme: 'light' })

test('R-TH-08: the preview shows every theme with its own token values', async ({ page }) => {
  await openPreview(page)

  const backgrounds = await page.evaluate(() =>
    Object.fromEntries(
      [...document.querySelectorAll<HTMLElement>('[data-testid^="theme-"]')].map((column) => [
        column.dataset.theme,
        getComputedStyle(column).backgroundColor,
      ]),
    ),
  )

  expect(backgrounds).toEqual({ light: 'rgb(246, 247, 249)', dark: 'rgb(14, 16, 20)' })
})

test('R-TH-08: each sample really takes the value of its token in each theme', async ({ page }) => {
  await openPreview(page)

  const read = (theme: string, token: string, property: string): Promise<string> =>
    page.evaluate(
      ([themeName, tokenName, propertyName]) => {
        const sample = document.querySelector(
          `[data-theme="${themeName}"] [data-token="${tokenName}"] [style]`,
        )
        return getComputedStyle(sample as Element).getPropertyValue(propertyName as string)
      },
      [theme, token, property],
    )

  expect(await read('dark', '--ytm-color-accent', 'background-color')).toBe('rgb(91, 155, 255)')
  expect(await read('light', '--ytm-color-accent', 'background-color')).toBe('rgb(31, 95, 209)')
  expect(await read('light', '--ytm-font-size-display-lg', 'font-size')).toBe('52px')
  expect(await read('light', '--ytm-font-size-title-sm', 'font-size')).toBe('15px')
  expect(await read('dark', '--ytm-font-weight-semibold', 'font-weight')).toBe('600')
  expect(await read('dark', '--ytm-radius-sm', 'border-radius')).toBe('6px')
  expect(await read('dark', '--ytm-radius-xl', 'border-radius')).toBe('16px')
  expect(await read('light', '--ytm-font-heading', 'font-family')).toContain('Space Grotesk')
  expect(await read('dark', '--ytm-shadow-overlay', 'box-shadow')).not.toBe('none')
  expect(await read('light', '--ytm-shadow-raised', 'box-shadow')).not.toBe('none')
})

test('R-TH-08: the preview lists every token of the token file in both themes', async ({
  page,
}) => {
  await openPreview(page)

  const counts = await page.evaluate(() =>
    Object.fromEntries(
      [...document.querySelectorAll<HTMLElement>('[data-testid^="theme-"]')].map((column) => [
        column.dataset.theme,
        column.querySelectorAll('[data-token]').length,
      ]),
    ),
  )

  expect(counts.light).toBe(counts.dark)
  expect(counts.light).toBeGreaterThanOrEqual(51)
})

test('R-TH-09: the preview page looks as recorded, in both themes', async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 900 })
  await openPreview(page)

  await expect(page).toHaveScreenshot('theme-preview.png', { fullPage: true })
})

test('R-TH-08: the preview page is not part of the built app', async ({ request }) => {
  const response = await request.get('/theme-preview.html')

  expect(response.status()).toBe(404)
})
