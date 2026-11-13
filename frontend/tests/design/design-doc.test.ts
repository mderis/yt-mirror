import { describe, expect, it } from 'vitest'

import { groupOf, parseTokens, shortName } from '@/design/tokens'

import { DESIGN_DIR, read, REPO_ROOT } from '../helpers/files'

/**
 * docs/DESIGN.md section 2 documents every token and its value. These tests
 * read the tables there and compare them with tokens.css, so the document and
 * the code cannot disagree.
 */
const tokens = parseTokens(read(DESIGN_DIR, 'tokens.css'))
const doc = read(REPO_ROOT, 'docs', 'DESIGN.md')
const section = doc.slice(doc.indexOf('## 2. The theme center'), doc.indexOf('## 3. Rules for all'))

function rows(): string[][] {
  return section
    .split('\n')
    .filter((line) => line.startsWith('| `'))
    .map((line) =>
      line
        .split('|')
        .slice(1, -1)
        .map((cell) => cell.trim()),
    )
}

function codeSpans(cell: string): string[] {
  return [...cell.matchAll(/`([^`]+)`/g)].map((match) => match[1] ?? '')
}

function normalise(value: string): string {
  return value.toLowerCase().replace(/\s+/g, ' ').trim()
}

/** Rows whose second and third cells hold one value per theme: colours and shadows. */
function themedRows(): { name: string; dark: string; light: string }[] {
  return rows().flatMap((cells) => {
    const names = codeSpans(cells[0] ?? '')
    const dark = codeSpans(cells[1] ?? '')
    const light = codeSpans(cells[2] ?? '')
    if (dark.length === 0 || dark.length !== names.length || light.length !== names.length) {
      return []
    }
    return names.map((name, index) => ({
      name,
      dark: dark[index] ?? '',
      light: light[index] ?? '',
    }))
  })
}

/** Rows whose second cell is one plain value for all themes, for example "14 px" or "400". */
function sharedRows(): { name: string; value: string }[] {
  return rows().flatMap((cells) => {
    const names = codeSpans(cells[0] ?? '')
    const value = /^(\d+(?:\.\d+)?)\s?(px|ms)?$/.exec(cells[1] ?? '')
    if (names.length !== 1 || value === null) {
      return []
    }
    return [{ name: names[0] ?? '', value: `${value[1]}${value[2] ?? ''}` }]
  })
}

function themed(theme: string, group: string): Record<string, string> {
  return Object.fromEntries(
    [...(tokens.themes.get(theme) ?? [])]
      .filter(([name]) => groupOf(name) === group)
      .map(([name, value]) => [shortName(name), normalise(value)]),
  )
}

describe('docs/DESIGN.md section 2 and tokens.css', () => {
  it('R-TH-02: document the same colours with the same values, in both themes', () => {
    const documented = themedRows().filter((row) => row.dark.startsWith('#'))

    expect(documented.length).toBe(21)
    expect(themed('dark', 'color')).toEqual(
      Object.fromEntries(documented.map((row) => [row.name, normalise(row.dark)])),
    )
    expect(themed('light', 'color')).toEqual(
      Object.fromEntries(documented.map((row) => [row.name, normalise(row.light)])),
    )
  })

  it('R-TH-02: document the same shadows with the same values, in both themes', () => {
    const documented = themedRows().filter((row) => row.name.startsWith('shadow-'))
    const strip = (name: string): string => name.replace(/^shadow-/, '')

    expect(documented.map((row) => row.name)).toEqual(['shadow-raised', 'shadow-overlay'])
    expect(themed('dark', 'shadow')).toEqual(
      Object.fromEntries(documented.map((row) => [strip(row.name), normalise(row.dark)])),
    )
    expect(themed('light', 'shadow')).toEqual(
      Object.fromEntries(documented.map((row) => [strip(row.name), normalise(row.light)])),
    )
  })

  it('R-TH-02: document the same sizes, weights, line heights, radii, spacing and durations', () => {
    const documented = Object.fromEntries(sharedRows().map((row) => [row.name, row.value]))
    const actual = Object.fromEntries(
      [...tokens.shared]
        .filter(
          ([name]) =>
            !['font', 'radius'].includes(groupOf(name) ?? '') ||
            /px$/.test(tokens.shared.get(name) ?? ''),
        )
        .filter(([name]) => name !== '--ytm-radius-full')
        .map(([name, value]) => [name.replace('--ytm-', ''), value]),
    )

    expect(Object.keys(documented).length).toBe(24)
    expect(actual).toEqual(documented)
  })

  it('R-TH-02: document every font family token and the fully round radius', () => {
    for (const name of ['font-text', 'font-heading', 'font-mono', 'radius-full']) {
      expect(section, name).toContain(`| \`${name}\` |`)
    }
  })
})
