import { describe, expect, it } from 'vitest'

import { THEME_NAMES } from '@/design/themes'
import {
  allTokenNames,
  groupOf,
  parseTokens,
  shortName,
  TOKEN_GROUPS,
  TOKEN_PREFIX,
} from '@/design/tokens'

import { DESIGN_DIR, exists, list, read } from '../helpers/files'

const tokens = parseTokens(read(DESIGN_DIR, 'tokens.css'))
const themeNames = [...tokens.themes.keys()].sort()
const everyName = [...allTokenNames(tokens)]

function px(name: string): number {
  const value = tokens.shared.get(name) ?? ''
  expect(value, name).toMatch(/^\d+px$/)
  return Number.parseInt(value, 10)
}

describe('tokens.css', () => {
  it('R-TH-04: has exactly one block per theme of themes.ts, and both lists agree', () => {
    expect(themeNames).toEqual([...THEME_NAMES].sort())
    expect(themeNames).toEqual(['dark', 'light'])
  })

  it('R-TH-04: every theme defines exactly the same tokens', () => {
    const [first, ...others] = themeNames.map((theme) =>
      [...(tokens.themes.get(theme)?.keys() ?? [])].sort(),
    )

    expect(first?.length).toBeGreaterThan(0)
    for (const other of others) {
      expect(other).toEqual(first)
    }
  })

  it('R-TH-04: a theme block holds the colours and shadows, and nothing is defined twice', () => {
    for (const theme of tokens.themes.values()) {
      for (const name of theme.keys()) {
        expect(['color', 'shadow'], name).toContain(groupOf(name))
        expect(tokens.shared.has(name), `${name} is also a shared token`).toBe(false)
      }
    }
    for (const name of tokens.shared.keys()) {
      expect(['color', 'shadow'], name).not.toContain(groupOf(name))
    }
  })

  it('R-TH-02: every token is named --ytm-<group>-<name> and every group has tokens', () => {
    for (const name of everyName) {
      expect(name, name).toMatch(/^--ytm-[a-z]+(-[a-z]+)*$/)
      expect(groupOf(name), `${name} fits no token group`).not.toBeNull()
    }
    for (const group of TOKEN_GROUPS) {
      const members = everyName.filter((name) => groupOf(name) === group)
      expect(members.length, `group ${group} is empty`).toBeGreaterThan(0)
    }
  })

  it('R-TH-03: token names are semantic, never a colour word or a number', () => {
    const valueWords =
      /(^|-)(blue|red|green|gr[ae]y|orange|yellow|purple|pink|black|white|navy|slate|amber)(-|$)|\d/

    for (const name of everyName) {
      expect(shortName(name), name).not.toMatch(valueWords)
    }
  })

  it('R-TH-02: the font size scale is the one the maintainer decided', () => {
    const sizes = Object.fromEntries(
      everyName
        .filter((name) => groupOf(name) === 'font-size')
        .map((name) => [shortName(name), px(name)]),
    )

    expect(sizes).toEqual({
      label: 12,
      meta: 13,
      body: 14,
      'title-sm': 15,
      'body-lg': 16,
      'heading-sm': 18,
      'heading-md': 22,
      'heading-lg': 28,
      'display-md': 36,
      'display-lg': 52,
    })
  })

  it('R-TH-02: the radius scale is the one the maintainer decided', () => {
    const radii = Object.fromEntries(
      everyName
        .filter((name) => groupOf(name) === 'radius')
        .map((name) => [shortName(name), px(name)]),
    )

    expect(radii).toEqual({ xs: 4, sm: 6, md: 8, lg: 12, xl: 16, full: 9999 })
  })

  it('R-TH-02: the spacing step is 4 px and is a single token', () => {
    expect(everyName.filter((name) => groupOf(name) === 'space')).toEqual(['--ytm-space'])
    expect(px('--ytm-space')).toBe(4)
    expect(shortName('--ytm-space')).toBe('space')
  })

  it('R-TH-02: animations take no time when the system asks for reduced motion', () => {
    const durations = everyName.filter((name) => groupOf(name) === 'duration').sort()

    expect(durations).toEqual(['--ytm-duration-base', '--ytm-duration-fast'])
    expect([...tokens.reducedMotion.keys()].sort()).toEqual(durations)
    expect([...tokens.reducedMotion.values()]).toEqual(['0ms', '0ms'])
  })

  it('R-TH-07: the file is plain CSS that the website can import as it is', () => {
    const css = read(DESIGN_DIR, 'tokens.css')

    expect(css).not.toMatch(/@(import|theme|apply|utility|layer|source)\b/)
    expect(css).not.toMatch(/url\(/)
  })
})

describe('the token parser', () => {
  it('R-TH-02: reads shared, per-theme and reduced-motion values', () => {
    const parsed = parseTokens(`
      /* a comment with { braces } */
      :root { --ytm-space: 4px; --ytm-duration-fast: 150ms; }
      @media (prefers-reduced-motion: reduce) { :root { --ytm-duration-fast: 0ms; } }
      [data-theme='dark'] { --ytm-color-bg: #000; }
      [data-theme="light"] { --ytm-color-bg: #fff; }
    `)

    expect(Object.fromEntries(parsed.shared)).toEqual({
      '--ytm-space': '4px',
      '--ytm-duration-fast': '150ms',
    })
    expect(Object.fromEntries(parsed.reducedMotion)).toEqual({ '--ytm-duration-fast': '0ms' })
    expect([...parsed.themes.keys()]).toEqual(['dark', 'light'])
    expect(parsed.themes.get('light')?.get('--ytm-color-bg')).toBe('#fff')
  })

  it('R-TH-01: rejects anything that is not a block of custom properties', () => {
    expect(() => parseTokens('body { --ytm-space: 4px; }')).toThrow(/only :root and \[data-theme\]/)
    expect(() => parseTokens(':root { color: red; }')).toThrow(/only custom properties/)
    expect(() => parseTokens(':root { --ytm-space: 4px; } stray text')).toThrow(
      /outside its blocks/,
    )
    expect(() => parseTokens(':root { --ytm-space: 4px; oops }')).toThrow(/not a declaration/)
  })

  it('R-TH-02: knows the group and the short name of a token', () => {
    expect(groupOf('--ytm-font-size-body')).toBe('font-size')
    expect(groupOf('--ytm-font-weight-medium')).toBe('font-weight')
    expect(groupOf('--ytm-font-text')).toBe('font')
    expect(groupOf('--ytm-color-text-muted')).toBe('color')
    expect(groupOf('--ytm-unknown-thing')).toBeNull()
    expect(groupOf('--other-color-bg')).toBeNull()
    expect(shortName('--ytm-color-text-muted')).toBe('text-muted')
    expect(shortName('--other-thing')).toBe('--other-thing')
    expect(TOKEN_PREFIX).toBe('--ytm-')
  })
})

describe('the bundled fonts', () => {
  const fontFolders = list(DESIGN_DIR, 'fonts').filter((name) => !name.includes('.'))
  const declared = fontFolders.map((folder) => ({
    folder,
    css: read(DESIGN_DIR, 'fonts', folder, 'font.css'),
  }))

  it('R-TH-05: every font folder has its declarations, its files and its license', () => {
    expect(fontFolders).toEqual(['inter', 'space-grotesk'])
    for (const { folder, css } of declared) {
      const files = [...css.matchAll(/url\(\.\/([^)]+)\)/g)].map((match) => match[1] ?? '')

      expect(files.length, folder).toBeGreaterThan(0)
      for (const file of files) {
        expect(exists(DESIGN_DIR, 'fonts', folder, file), `${folder}/${file}`).toBe(true)
      }
      expect(read(DESIGN_DIR, 'fonts', folder, 'LICENSE.txt')).toContain('SIL Open Font License')
    }
  })

  it('R-TH-05: the font named first in each font token is one of the bundled fonts', () => {
    const bundled = new Set(
      declared.flatMap(({ css }) =>
        [...css.matchAll(/font-family:\s*'([^']+)'/g)].map((match) => match[1]),
      ),
    )
    const system = new Set(['system-ui', 'ui-monospace', 'sans-serif', 'monospace'])
    const fontTokens = everyName.filter((name) => groupOf(name) === 'font')

    expect(fontTokens.sort()).toEqual(['--ytm-font-heading', '--ytm-font-mono', '--ytm-font-text'])
    for (const name of fontTokens) {
      const families = (tokens.shared.get(name) ?? '')
        .split(',')
        .map((family) => family.trim().replace(/^'|'$/g, ''))
      for (const family of families) {
        expect(bundled.has(family) || system.has(family), `${name}: ${family}`).toBe(true)
      }
    }
    expect(tokens.shared.get('--ytm-font-text')).toMatch(/^'Inter Variable'/)
    expect(tokens.shared.get('--ytm-font-heading')).toMatch(/^'Space Grotesk Variable'/)
  })

  it('R-TH-05: no font or stylesheet is loaded from the network', () => {
    const stylesheets = ['tokens.css', 'theme.css', 'base.css', 'index.css']
    const all = [
      ...stylesheets.map((file) => read(DESIGN_DIR, file)),
      ...declared.map(({ css }) => css),
    ]

    for (const css of all) {
      expect(css).not.toMatch(/https?:\/\//)
    }
  })
})
