import { expect, test, type Locator, type Page } from '@playwright/test'

import { PREVIEW_URL } from '../settings'

/**
 * The checkbox and the arrow of the select are drawn from tokens, not by the
 * system (docs/DESIGN.md section 4, "Form controls"), as the radio is. The
 * checkbox stays a real checkbox input and the select a real select: the
 * keyboard, labels and screen readers work as the system's. Checked in both
 * themes of the theme preview, in the real browsers.
 */

async function openPreview(page: Page): Promise<void> {
  await page.goto(`${PREVIEW_URL}/theme-preview.html`)
  await expect(page.getByRole('heading', { level: 1, name: 'Theme preview' })).toBeVisible()
}

/** The value of a colour token in a column, as the browser computes a colour. */
async function token(column: Locator, name: string): Promise<string> {
  return column.evaluate((element, variable) => {
    const probe = document.createElement('span')
    probe.style.color = `var(${variable})`
    element.append(probe)
    const colour = getComputedStyle(probe).color
    probe.remove()
    return colour
  }, name)
}

async function style(element: Locator, property: string, pseudo?: string): Promise<string> {
  return element.evaluate(
    (node, [name, after]) => getComputedStyle(node, after ?? null).getPropertyValue(name ?? ''),
    [property, pseudo] as const,
  )
}

function boxes(column: Locator): {
  off: Locator
  on: Locator
  mixed: Locator
  disabled: Locator
  disabledOn: Locator
} {
  const section = column.locator('[data-component="checkbox"]')
  const named = section.getByRole('checkbox', { name: 'Auto-mirror' })
  return {
    off: named.nth(0),
    on: named.nth(1),
    mixed: section.getByRole('checkbox', { name: 'Select all shown' }),
    disabled: named.nth(2),
    disabledOn: named.nth(3),
  }
}

for (const theme of ['light', 'dark']) {
  test(`R-TH-06, R-UI-14: the checkbox is drawn from the tokens of the ${theme} theme`, async ({
    page,
  }) => {
    await openPreview(page)
    const column = page.getByTestId(`theme-${theme}`)
    const { off, on, mixed, disabled, disabledOn } = boxes(column)

    expect(await style(off, 'appearance')).toBe('none')
    // Not ticked: a frame in the muted text colour on the surface.
    expect(await style(off, 'border-top-color')).toBe(await token(column, '--ytm-color-text-muted'))
    expect(await style(off, 'background-color')).toBe(await token(column, '--ytm-color-surface'))
    // Ticked: the accent, with a check mark in the colour on the accent.
    await expect(on).toBeChecked()
    expect(await style(on, 'background-color')).toBe(await token(column, '--ytm-color-accent'))
    expect(await style(on, 'border-right-color', '::after')).toBe(
      await token(column, '--ytm-color-on-accent'),
    )
    // Mixed: the accent with a bar.
    expect(await mixed.evaluate((node) => (node as HTMLInputElement).indeterminate)).toBe(true)
    expect(await style(mixed, 'background-color')).toBe(await token(column, '--ytm-color-accent'))
    expect(await style(mixed, 'background-color', '::after')).toBe(
      await token(column, '--ytm-color-on-accent'),
    )
    // Disabled, ticked or not.
    await expect(disabled).toBeDisabled()
    expect(await style(disabled, 'border-top-color')).toBe(
      await token(column, '--ytm-color-line-strong'),
    )
    expect(await style(disabledOn, 'background-color')).toBe(
      await token(column, '--ytm-color-line-strong'),
    )
    // Under the pointer, a free box shows the accent, once its short transition ends.
    await off.hover()
    const accent = await token(column, '--ytm-color-accent')
    await expect.poll(() => style(off, 'border-top-color')).toBe(accent)
  })

  test(`R-TH-06, R-UI-14: the arrow of the select is drawn from the ${theme} theme`, async ({
    page,
  }) => {
    await openPreview(page)
    const column = page.getByTestId(`theme-${theme}`)
    const select = column.getByRole('combobox', { name: 'Quality' })
    const arrow = column.locator('[data-component="field"] [data-arrow]')

    expect(await style(select, 'appearance')).toBe('none')
    await expect(arrow).toBeVisible()
    expect(await style(arrow, 'color')).toBe(await token(column, '--ytm-color-text-muted'))
  })
}

test('R-UI-14: with "Increase contrast" of macOS the frame takes the text colour', async ({
  page,
}) => {
  await page.emulateMedia({ contrast: 'more' })
  await openPreview(page)

  for (const theme of ['light', 'dark']) {
    const column = page.getByTestId(`theme-${theme}`)
    const { off, disabled } = boxes(column)
    expect(await style(off, 'border-top-color')).toBe(await token(column, '--ytm-color-text'))
    expect(await style(disabled, 'border-top-color')).toBe(
      await token(column, '--ytm-color-text-muted'),
    )
  }
})

test('R-UI-14: with "Reduce motion" of macOS the checkbox changes without a transition', async ({
  page,
}) => {
  await openPreview(page)
  const { off } = boxes(page.getByTestId('theme-light'))
  expect(await style(off, 'transition-duration')).not.toMatch(/^0s/)

  await page.emulateMedia({ reducedMotion: 'reduce' })

  expect(await style(off, 'transition-duration')).toMatch(/^0s/)
})

test('R-UI-13: Space ticks a focused checkbox, which shows its focus ring', async ({ page }) => {
  await openPreview(page)
  const column = page.getByTestId('theme-light')
  const { off } = boxes(column)

  await off.focus()
  await expect(off).toBeFocused()
  expect(await style(off, 'outline-style')).toBe('solid')
  expect(await style(off, 'outline-color')).toBe(await token(column, '--ytm-color-accent'))
  await page.keyboard.press('Space')

  await expect(off).toBeChecked()
})

test('R-UI-13: the select keeps its focus ring when the keyboard reaches it', async ({ page }) => {
  await openPreview(page)
  const column = page.getByTestId('theme-dark')
  const select = column.getByRole('combobox', { name: 'Quality' })

  await select.focus()

  expect(await style(select, 'outline-style')).toBe('solid')
  expect(await style(select, 'outline-color')).toBe(await token(column, '--ytm-color-accent'))
})
