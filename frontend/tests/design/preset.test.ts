import { describe, expect, it } from 'vitest'

import { allTokenNames, groupOf, parseTokens } from '@/design/tokens'

import { DESIGN_DIR, read } from '../helpers/files'

const tokens = allTokenNames(parseTokens(read(DESIGN_DIR, 'tokens.css')))
const preset = read(DESIGN_DIR, 'theme.css')
const base = read(DESIGN_DIR, 'base.css')

describe('the Tailwind preset (theme.css)', () => {
  it('R-TH-01: maps every token to a utility class, so no token is unreachable', () => {
    for (const name of tokens) {
      expect(preset.includes(`var(${name})`), `${name} is not mapped in theme.css`).toBe(true)
    }
  })

  it('R-TH-06: switches off the palette and scales of Tailwind itself', () => {
    const namespaces = ['color', 'font', 'text', 'font-weight', 'leading', 'radius', 'shadow']

    for (const namespace of namespaces) {
      expect(preset, namespace).toContain(`--${namespace}-*: initial;`)
    }
  })

  it('R-TH-02: takes every value from a token and contains no value of its own', () => {
    const declarations = [...preset.matchAll(/^\s*(--[a-z-]+|transition-duration):\s*([^;]+);/gm)]

    expect(declarations.length).toBeGreaterThan(40)
    for (const [, property, value] of declarations) {
      expect(value === 'initial' || /^var\(--ytm-[a-z-]+\)$/.test(value ?? ''), property).toBe(true)
    }
  })

  it('R-TH-02: the base styles use tokens for every colour and font value', () => {
    const visual = [
      ...base.matchAll(/^\s*(color|background-color|font-[a-z]+|line-height):\s*([^;]+);/gm),
    ]

    expect(visual.length).toBe(6)
    for (const [, property, value] of visual) {
      expect(value, property).toMatch(/^var\(--ytm-[a-z-]+\)$/)
      expect(groupOf((value ?? '').slice(4, -1)), property).not.toBeNull()
    }
  })
})
