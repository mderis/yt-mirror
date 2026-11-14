import { render, screen } from '@testing-library/vue'
import { describe, expect, it } from 'vitest'

import { ICON_NAMES } from '@/components/icons'
import { BrandIcon } from '@/design/brand'
import ThemePreview from '@/design/preview/ThemePreview.vue'
import { THEME_NAMES } from '@/design/themes'
import { parseTokens, TOKEN_GROUPS } from '@/design/tokens'
import { i18n } from '@/i18n'

import { DESIGN_DIR, read } from '../helpers/files'

const tokens = parseTokens(read(DESIGN_DIR, 'tokens.css'))

function renderPreview(): HTMLElement {
  return render(ThemePreview, { global: { plugins: [i18n] } }).container as HTMLElement
}

/** Every shared component has a place on the page, marked with its name. */
const SHOWN = [
  'button',
  'icon',
  'progress',
  'banner',
  'more-buttons',
  'chip',
  'field',
  'menu',
  'dialog',
  'sidebar-item',
  'video-row',
  'skeleton',
  'empty',
]

describe('the theme preview page', () => {
  it('R-TH-08: shows every theme side by side, each under its own data-theme attribute', () => {
    renderPreview()

    for (const theme of THEME_NAMES) {
      const column = screen.getByTestId(`theme-${theme}`)

      expect(column.dataset.theme).toBe(theme)
      expect(column.textContent).toContain(`Theme: ${theme}`)
    }
  })

  it('R-TH-08: shows every token of tokens.css in every theme, with its value', () => {
    renderPreview()

    for (const theme of THEME_NAMES) {
      const column = screen.getByTestId(`theme-${theme}`)
      const expected = new Map([...tokens.shared, ...(tokens.themes.get(theme) ?? [])])
      const shown = [...column.querySelectorAll<HTMLElement>('[data-token]')]

      expect(shown.map((row) => row.dataset.token).sort()).toEqual([...expected.keys()].sort())
      for (const row of shown) {
        expect(row.textContent).toContain(expected.get(row.dataset.token ?? ''))
      }
    }
  })

  it('R-TH-08: groups the tokens under a heading per token group', () => {
    const container = renderPreview()
    const dark = container.querySelector('[data-theme="dark"]')

    for (const group of TOKEN_GROUPS) {
      const section = dark?.querySelector(`[data-group="${group}"]`)

      expect(section?.querySelector('h3')?.textContent?.trim(), group).toBeTruthy()
      expect(section?.querySelectorAll('[data-token]').length, group).toBeGreaterThan(0)
    }
    expect(dark?.querySelector('[data-group="color"] h3')?.textContent).toContain('Colours')
  })

  it('R-TH-08: every sample is drawn with its own token', () => {
    const container = renderPreview()
    const sample = (token: string): string =>
      container
        .querySelector(`[data-theme="light"] [data-token="${token}"] [style]`)
        ?.getAttribute('style') ?? ''

    expect(sample('--ytm-color-accent')).toContain('background-color: var(--ytm-color-accent)')
    expect(sample('--ytm-font-size-heading-lg')).toContain('var(--ytm-font-size-heading-lg)')
    expect(sample('--ytm-font-weight-semibold')).toContain('var(--ytm-font-weight-semibold)')
    expect(sample('--ytm-font-heading')).toContain('var(--ytm-font-heading)')
    expect(sample('--ytm-line-height-prose')).toContain('var(--ytm-line-height-prose)')
    expect(sample('--ytm-space')).toContain('calc(var(--ytm-space) * 1)')
    expect(sample('--ytm-radius-xl')).toContain('var(--ytm-radius-xl)')
    expect(sample('--ytm-shadow-overlay')).toContain('var(--ytm-shadow-overlay)')
    expect(sample('--ytm-duration-fast')).toContain('var(--ytm-duration-fast)')
  })

  it('R-TH-08: tells what a duration becomes under reduced motion', () => {
    renderPreview()

    const row = screen.getByTestId('theme-dark').querySelector('[data-token="--ytm-duration-base"]')

    expect(row?.textContent).toContain('With reduced motion: 0ms')
  })

  it('R-TH-08: shows every shared component in every theme, and the brand icon', () => {
    const container = renderPreview()

    for (const theme of ['dark', 'light']) {
      const components = container.querySelector(
        `[data-theme="${theme}"] [data-group="components"]`,
      )
      for (const component of SHOWN) {
        expect(
          components?.querySelector(`[data-component="${component}"]`),
          `${component} in ${theme}`,
        ).not.toBeNull()
      }
      expect(components?.querySelectorAll('[role="progressbar"]').length, theme).toBe(2)
      expect(components?.querySelector('[role="alert"]')?.textContent, theme).toContain(
        'Deno could not be installed',
      )
      expect(components?.querySelectorAll('[data-tone]').length, theme).toBeGreaterThanOrEqual(5)
      expect(components?.querySelector('[data-date="waiting"]')?.textContent, theme).toContain(
        'around 2005',
      )
      expect(
        [...(components?.querySelectorAll('[data-component="icon"] svg') ?? [])].map((icon) =>
          icon.getAttribute('data-icon'),
        ),
        theme,
      ).toEqual(ICON_NAMES)
    }
    expect(
      container.querySelector('[data-theme="dark"]')?.querySelectorAll('[data-group="brand"] svg')
        .length,
    ).toBe(2)
  })
})

describe('the brand icon', () => {
  it('R-TH-01: is drawn from icon.svg and takes its colours from the accent tokens', () => {
    const source = read(DESIGN_DIR, 'brand', 'icon.svg')
    const { container } = render(BrandIcon, { props: { label: 'yt-mirror' } })
    const colours = [...source.matchAll(/(?:fill|stroke)="([^"]+)"/g)].map((match) => match[1])

    expect(container.querySelector('svg')?.getAttribute('viewBox')).toBe('0 0 120 120')
    expect(new Set(colours)).toEqual(
      new Set(['var(--ytm-color-accent)', 'var(--ytm-color-on-accent)', 'none']),
    )
  })

  it('R-UI-14: has an accessible name when it stands alone, and is hidden when decorative', () => {
    const named = render(BrandIcon, { props: { label: 'yt-mirror' } }).container.firstElementChild
    const decorative = render(BrandIcon).container.firstElementChild

    expect(named?.getAttribute('role')).toBe('img')
    expect(named?.getAttribute('aria-label')).toBe('yt-mirror')
    expect(decorative?.getAttribute('aria-hidden')).toBe('true')
    expect(decorative?.hasAttribute('role')).toBe(false)
  })
})
