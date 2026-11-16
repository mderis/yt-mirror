import { expect, test, type Locator, type Page } from '@playwright/test'

import { PREVIEW_URL } from '../settings'

/**
 * The radio button is drawn from tokens, not by the system (docs/DESIGN.md
 * section 4, "Form controls"), and stays a real radio input: the keyboard,
 * labels and screen readers work as the system's. Checked in both themes of
 * the theme preview, in the real browsers.
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

async function style(radio: Locator, property: string): Promise<string> {
  return radio.evaluate(
    (element, name) => getComputedStyle(element).getPropertyValue(name),
    property,
  )
}

function radios(column: Locator): {
  pick: Locator
  all: Locator
  later: Locator
  offChecked: Locator
} {
  const choice = column.getByRole('group', { name: 'What to mirror' })
  const off = column.getByRole('group', { name: 'Not available now' })
  return {
    pick: choice.getByRole('radio', { name: 'Let me pick videos myself' }),
    all: choice.getByRole('radio', { name: /Mirror everything/ }),
    later: choice.getByRole('radio', { name: /only videos uploaded on or after/ }),
    offChecked: off.getByRole('radio', { name: 'Let me pick videos myself' }),
  }
}

for (const theme of ['light', 'dark']) {
  test(`R-TH-06, R-UI-14: the radio is drawn from the tokens of the ${theme} theme`, async ({
    page,
  }) => {
    await openPreview(page)
    const column = page.getByTestId(`theme-${theme}`)
    const { pick, all, later, offChecked } = radios(column)

    expect(await style(all, 'appearance')).toBe('none')
    // Not chosen: a ring in the muted text colour on the surface.
    expect(await style(all, 'border-top-color')).toBe(await token(column, '--ytm-color-text-muted'))
    expect(await style(all, 'background-color')).toBe(await token(column, '--ytm-color-surface'))
    // Chosen: the accent, with a dot in the colour on the accent.
    await expect(pick).toBeChecked()
    expect(await style(pick, 'border-top-color')).toBe(await token(column, '--ytm-color-accent'))
    expect(await style(pick, 'background-color')).toBe(await token(column, '--ytm-color-on-accent'))
    expect(await style(pick, 'box-shadow')).toContain(await token(column, '--ytm-color-accent'))
    // Disabled, chosen or not.
    await expect(later).toBeDisabled()
    expect(await style(later, 'border-top-color')).toBe(
      await token(column, '--ytm-color-line-strong'),
    )
    expect(await style(later, 'background-color')).toBe(
      await token(column, '--ytm-color-neutral-bg'),
    )
    expect(await style(offChecked, 'box-shadow')).toContain(
      await token(column, '--ytm-color-line-strong'),
    )
    // Under the pointer, a free option shows the accent, once its short transition ends.
    await all.hover()
    const accent = await token(column, '--ytm-color-accent')
    await expect.poll(() => style(all, 'border-top-color')).toBe(accent)
  })
}

test('R-UI-14: with "Increase contrast" of macOS the ring takes the text colour', async ({
  page,
}) => {
  await page.emulateMedia({ contrast: 'more' })
  await openPreview(page)

  for (const theme of ['light', 'dark']) {
    const column = page.getByTestId(`theme-${theme}`)
    const { all, later } = radios(column)
    expect(await style(all, 'border-top-color')).toBe(await token(column, '--ytm-color-text'))
    expect(await style(later, 'border-top-color')).toBe(
      await token(column, '--ytm-color-text-muted'),
    )
  }
})

test('R-UI-14: with "Reduce motion" of macOS the radio changes without a transition', async ({
  page,
}) => {
  await openPreview(page)
  const { all } = radios(page.getByTestId('theme-light'))
  expect(await style(all, 'transition-duration')).not.toMatch(/^0s/)

  await page.emulateMedia({ reducedMotion: 'reduce' })

  expect(await style(all, 'transition-duration')).toMatch(/^0s/)
})

test('R-UI-13: arrow keys move between options, skip a disabled one, and show the focus ring', async ({
  page,
}) => {
  await openPreview(page)
  const column = page.getByTestId('theme-light')
  const { pick, all, later } = radios(column)

  // Whether Tab reaches a radio in WebKit is a setting of macOS ("Keyboard navigation"), so
  // the test starts on the chosen option. The ring follows :focus, however it came there.
  await pick.focus()
  await expect(pick).toBeFocused()
  expect(await style(pick, 'outline-style')).toBe('solid')
  await page.keyboard.press('ArrowDown')

  // The ring stays when the arrow keys move it (WebKit drops :focus-visible there).
  await expect(all).toBeFocused()
  await expect(all).toBeChecked()
  expect(await style(all, 'outline-style')).toBe('solid')
  expect(await style(all, 'outline-color')).toBe(await token(column, '--ytm-color-accent'))

  // The keys never reach the disabled option. (WebKit stops at the last free option,
  // Chromium wraps to the first: either way the focused option is the chosen one.)
  await page.keyboard.press('ArrowDown')

  await expect(later).not.toBeChecked()
  await expect(later).not.toBeFocused()
  const group = column.getByRole('group', { name: 'What to mirror' })
  await expect(group.getByRole('radio', { checked: true })).toBeFocused()
})

test('R-UI-13: a click on the text of an option chooses it; a disabled option cannot be chosen', async ({
  page,
}) => {
  await openPreview(page)
  const column = page.getByTestId('theme-dark')
  const group = column.getByRole('group', { name: 'What to mirror' })
  const { pick, all, later } = radios(column)

  await group.getByText('Mirror everything and keep it in sync (auto-mirror)').click()
  await expect(all).toBeChecked()

  // Clicked as a user can, though Playwright would wait for it to become enabled.
  await group
    .getByText('Auto-mirror, but only videos uploaded on or after a date')
    .click({ force: true })

  await expect(later).not.toBeChecked()
  await expect(all).toBeChecked()
  await expect(pick).not.toBeChecked()
})
