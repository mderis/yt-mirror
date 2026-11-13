/**
 * Reads tokens.css into data. Implements part of R-TH-02 and R-TH-09.
 *
 * Used by the theme preview page (to show every token), by the tests (to
 * check the rules of docs/DESIGN.md section 2.1) and by the theme lint (to
 * know which tokens exist). It must stay free of browser and Node APIs so
 * that all three can import it.
 */

/** The groups a token can belong to, in display order. Longer names first where one starts another. */
export const TOKEN_GROUPS = [
  'color',
  'font-size',
  'font-weight',
  'font',
  'line-height',
  'space',
  'radius',
  'shadow',
  'duration',
] as const

export type TokenGroup = (typeof TOKEN_GROUPS)[number]

/** The prefix of every token. */
export const TOKEN_PREFIX = '--ytm-'

export interface ParsedTokens {
  /** Tokens with one value for all themes: name to value. */
  shared: Map<string, string>
  /** Tokens of each theme: theme name, then token name to value. */
  themes: Map<string, Map<string, string>>
  /** Values that replace shared ones when the system asks for reduced motion. */
  reducedMotion: Map<string, string>
}

const COMMENT = /\/\*[\s\S]*?\*\//g
const REDUCED_MOTION =
  /@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{\s*:root\s*\{([^{}]*)\}\s*\}/g
const BLOCK = /([^{}]+)\{([^{}]*)\}/g
const DECLARATION = /([^:;{}\s][^:;{}]*):([^;{}]+);/g
const THEME_SELECTOR = /^\[data-theme=['"]([a-z0-9-]+)['"]\]$/

/**
 * Parse the text of tokens.css.
 *
 * @param css - The content of tokens.css.
 * @returns The tokens by block.
 * @throws Error when the file contains anything other than the documented blocks of custom properties.
 */
export function parseTokens(css: string): ParsedTokens {
  const result: ParsedTokens = { shared: new Map(), themes: new Map(), reducedMotion: new Map() }
  let text = css.replace(COMMENT, '')
  text = text.replace(REDUCED_MOTION, (_whole, body: string) => {
    readDeclarations(body, result.reducedMotion)
    return ''
  })
  let rest = text
  for (const match of text.matchAll(BLOCK)) {
    const selector = (match[1] ?? '').trim()
    const body = match[2] ?? ''
    rest = rest.replace(match[0], '')
    if (selector === ':root') {
      readDeclarations(body, result.shared)
      continue
    }
    const theme = THEME_SELECTOR.exec(selector)?.[1]
    if (theme === undefined) {
      throw new Error(
        `tokens.css may contain only :root and [data-theme] blocks, found "${selector}"`,
      )
    }
    const tokens = result.themes.get(theme) ?? new Map<string, string>()
    readDeclarations(body, tokens)
    result.themes.set(theme, tokens)
  }
  if (rest.trim() !== '') {
    throw new Error(`tokens.css contains text outside its blocks: "${rest.trim().slice(0, 60)}"`)
  }
  return result
}

/**
 * Return the group of a token, or null when its name fits no group.
 *
 * @param name - The full variable name, for example `--ytm-font-size-body`.
 */
export function groupOf(name: string): TokenGroup | null {
  if (!name.startsWith(TOKEN_PREFIX)) {
    return null
  }
  const rest = name.slice(TOKEN_PREFIX.length)
  return TOKEN_GROUPS.find((group) => rest === group || rest.startsWith(`${group}-`)) ?? null
}

/**
 * Return the name of a token inside its group, as used in docs/DESIGN.md.
 *
 * @param name - The full variable name, for example `--ytm-color-text-muted`.
 * @returns The short name, for example `text-muted`. A token that is its whole group returns the group.
 */
export function shortName(name: string): string {
  const group = groupOf(name)
  if (group === null) {
    return name
  }
  const rest = name.slice(TOKEN_PREFIX.length)
  return rest === group ? group : rest.slice(group.length + 1)
}

/**
 * Return the names of every token: the shared ones and those of all themes.
 *
 * @param tokens - The parsed tokens.
 */
export function allTokenNames(tokens: ParsedTokens): Set<string> {
  const names = new Set(tokens.shared.keys())
  for (const theme of tokens.themes.values()) {
    for (const name of theme.keys()) {
      names.add(name)
    }
  }
  return names
}

function readDeclarations(body: string, into: Map<string, string>): void {
  let rest = body
  for (const match of body.matchAll(DECLARATION)) {
    const name = (match[1] ?? '').trim()
    rest = rest.replace(match[0], '')
    if (!name.startsWith('--')) {
      throw new Error(`tokens.css may contain only custom properties, found "${name}"`)
    }
    into.set(name, (match[2] ?? '').trim())
  }
  if (rest.trim() !== '') {
    throw new Error(
      `tokens.css has a line that is not a declaration: "${rest.trim().slice(0, 60)}"`,
    )
  }
}
