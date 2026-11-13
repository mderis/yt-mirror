import { describe, expect, it, vi } from 'vitest'

import { applyTheme, resolveTheme, THEME_NAMES, THEMES } from '@/design/themes'

/** A stand-in for the system appearance that tests can switch. */
class FakeSystem extends EventTarget {
  matches: boolean

  constructor(dark: boolean) {
    super()
    this.matches = dark
  }

  switchTo(dark: boolean): void {
    this.matches = dark
    this.dispatchEvent(new Event('change'))
  }

  asMediaQuery(): MediaQueryList {
    return this as unknown as MediaQueryList
  }
}

function newRoot(): HTMLElement {
  return document.createElement('div')
}

describe('themes', () => {
  it('R-PL-05: there is a light and a dark theme', () => {
    expect(THEME_NAMES).toEqual(['light', 'dark'])
    expect(THEMES.dark.colorScheme).toBe('dark')
    expect(THEMES.light.colorScheme).toBe('light')
  })

  it('R-PL-05: "same as system" follows the system setting', () => {
    expect(resolveTheme('system', true)).toBe('dark')
    expect(resolveTheme('system', false)).toBe('light')
  })

  it('R-PL-05: an explicit choice wins over the system setting', () => {
    expect(resolveTheme('light', true)).toBe('light')
    expect(resolveTheme('dark', false)).toBe('dark')
  })

  it('R-TH-04: showing a theme sets one attribute on the root, which selects its token block', () => {
    const root = newRoot()

    applyTheme('dark', root, new FakeSystem(false).asMediaQuery())

    expect(root.dataset.theme).toBe('dark')
    expect(root.style.colorScheme).toBe('dark')
  })

  it('R-PL-05: with "same as system" the theme changes when the system changes', () => {
    const root = newRoot()
    const system = new FakeSystem(false)

    applyTheme('system', root, system.asMediaQuery())
    const before = root.dataset.theme
    system.switchTo(true)

    expect(before).toBe('light')
    expect(root.dataset.theme).toBe('dark')
    expect(root.style.colorScheme).toBe('dark')
  })

  it('R-PL-05: an explicit choice ignores later system changes', () => {
    const root = newRoot()
    const system = new FakeSystem(false)

    const stop = applyTheme('light', root, system.asMediaQuery())
    system.switchTo(true)
    stop()

    expect(root.dataset.theme).toBe('light')
  })

  it('R-PL-05: following the system can be stopped', () => {
    const root = newRoot()
    const system = new FakeSystem(false)

    const stop = applyTheme('system', root, system.asMediaQuery())
    stop()
    system.switchTo(true)

    expect(root.dataset.theme).toBe('light')
  })

  it('R-PL-05: by default the theme goes on the document and follows the browser', () => {
    const system = new FakeSystem(true)
    const matchMedia = vi.fn<typeof window.matchMedia>(() => system.asMediaQuery())
    vi.stubGlobal('matchMedia', matchMedia)

    const stop = applyTheme('system')
    stop()

    expect(matchMedia).toHaveBeenCalledWith('(prefers-color-scheme: dark)')
    expect(document.documentElement.dataset.theme).toBe('dark')
  })
})
