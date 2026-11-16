import { expect, test, type Locator, type Page } from '@playwright/test'

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

/**
 * One image per section and theme: each group of tokens, the brand icon, and
 * each shared component. A change shows up in the image of the section where
 * it happens, and the limit of differing pixels counts for that section only
 * (docs/TESTING.md section 6).
 */
for (const theme of ['light', 'dark']) {
  test(`R-TH-09: each section of the preview looks as recorded, ${theme} theme`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1600, height: 900 })
    await openPreview(page)
    const column = page.getByTestId(`theme-${theme}`)

    const sections: [string, Locator][] = [['heading', column.locator(':scope > h2')]]
    for (const section of await column.locator(':scope > section[data-group]').all()) {
      const group = await section.getAttribute('data-group')
      if (group !== 'components') sections.push([group ?? '', section])
    }
    for (const sample of await column.locator('[data-samples] > [data-component]').all()) {
      sections.push([`component-${await sample.getAttribute('data-component')}`, sample])
    }
    // Every sample has a name of its own, so none is left out of the images.
    await expect(column.locator('[data-samples] > :not([data-component])')).toHaveCount(0)
    expect(new Set(sections.map(([name]) => name)).size).toBe(sections.length)
    expect(sections.length).toBe(26)

    for (const [name, section] of sections) {
      await expect.soft(section, name).toHaveScreenshot(`theme-preview-${theme}-${name}.png`)
    }
  })
}

test('R-TH-09: the page heading of the preview looks as recorded', async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 900 })
  await openPreview(page)

  await expect(page.locator('header')).toHaveScreenshot('theme-preview-header.png')
})

test('R-TH-08: the preview page is not part of the built app', async ({ request }) => {
  const response = await request.get('/theme-preview.html')

  expect(response.status()).toBe(404)
})
