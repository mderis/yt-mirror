/**
 * The rules of the theme lint. Implements R-TH-06 and R-TH-09.
 *
 * Code outside the theme center (src/design/) may use only tokens. These
 * rules find everything else: raw colours, raw sizes, font declarations,
 * Tailwind arbitrary values, values off the spacing scale, utility classes
 * that do not exist in the theme, and references to tokens that are not
 * defined. This module is pure: it gets text and returns findings.
 */

export type RuleId =
  | 'raw-colour'
  | 'raw-size'
  | 'raw-font'
  | 'arbitrary-value'
  | 'off-scale'
  | 'unknown-class'
  | 'undefined-token'

export interface Finding {
  file: string
  line: number
  rule: RuleId
  message: string
}

export interface LintContext {
  /** The names of all defined tokens, for example `--ytm-color-accent`. */
  tokens: ReadonlySet<string>
  /** Whether a utility class exists in the Tailwind preset of the theme center. */
  isKnownClass: (name: string) => boolean
}

/** Which rules apply to a file. Files of the theme center are checked for undefined tokens only. */
export type Scope = 'code' | 'design'

const HEX_COLOUR = /(?<![\w&])#(?:[0-9a-f]{8}|[0-9a-f]{6}|[0-9a-f]{3,4})(?![\w-])/gi
const COLOUR_FUNCTION = /(?<![\w-])(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch)\(/g
const RAW_SIZE = /(?<![\w.#-])(\d*\.?\d+)(px|rem|em|pt)(?![\w-])/g
const ALLOWED_SIZES = new Set(['0px', '1px'])
const CSS_FONT = /(?<![\w-])(font-family|font-size|font-weight|line-height|font)\s*:\s*([^;}"']+)/g
const JS_FONT = /\b(fontFamily|fontSize|fontWeight|lineHeight)\s*:\s*([^,}\n]+)/g
const CSS_COLOUR =
  /(?<![\w-])(color|background-color|background|border-color|outline-color|fill|stroke|caret-color|accent-color)\s*:\s*([^;}"']+)/g
const TOKEN_REFERENCE = /var\(\s*(--ytm-[a-z0-9-]+)/g
const USES_TOKEN = /var\(\s*--ytm-/
const NEUTRAL_VALUE = /^(?:inherit|initial|unset|none|transparent|currentcolor|normal)$/i
const ARBITRARY_VALUE = /(?<![\w-])(?:[a-z][a-z0-9:/-]*-)\[[^\]\s]+\]/g
const ARBITRARY_PROPERTY = /(?<![\w-])\[[a-z-]+:[^\]\s]+\]/g
const ARBITRARY_VARIABLE = /(?<![\w-])(?:[a-z][a-z0-9:/-]*-)\(--[^)\s]*\)/g
const SPACING_UTILITIES =
  'p[xytrblse]?|m[xytrblse]?|gap(?:-[xy])?|space-[xy]|w|h|size|min-w|min-h|max-w|max-h|inset(?:-[xy])?|top|right|bottom|left|start|end|basis|indent|translate(?:-[xy])?'
// The scale is 2 px or a multiple of 4 px (docs/DESIGN.md section 2.4). Half a step, written
// 0.5, is the 2 px step. Every other fraction is off the scale.
const FRACTIONAL_SPACING = new RegExp(
  `(?<![\\w-])-?(?:[a-z-]+:)*(?:${SPACING_UTILITIES})-(?!0\\.5(?![\\w.-]))\\d+\\.\\d+(?![\\w-])`,
  'g',
)
const NUMERIC_LINE_HEIGHT = /(?<![\w-])(?:[a-z-]+:)*leading-\d+(?:\.\d+)?(?![\w-])/g
const NUMERIC_DURATION = /(?<![\w-])(?:[a-z-]+:)*duration-\d+(?![\w-])/g
const STATIC_CLASS = /(?<![:\w-])class="([^"]*)"/g
const BOUND_CLASS = /(?::class|v-bind:class)="([^"]*)"/g
const QUOTED = /'([^']*)'|`([^`]*)`/g
const STYLE_BLOCK = /<style\b[^>]*>[\s\S]*?<\/style>/g
const STYLE_ATTRIBUTE = /(?<![:\w-])style="[^"]*"/g

/**
 * Check the text of one file.
 *
 * @param file - The path shown in findings.
 * @param text - The content of the file.
 * @param scope - `code` for files outside the theme center, `design` for files inside it.
 * @param context - The defined tokens and the class check.
 * @returns The findings, in the order they appear in the file.
 */
export function checkText(
  file: string,
  text: string,
  scope: Scope,
  context: LintContext,
): Finding[] {
  const findings: Finding[] = []
  const add = (index: number, rule: RuleId, message: string): void => {
    findings.push({ file, line: lineAt(text, index), rule, message })
  }

  for (const match of text.matchAll(TOKEN_REFERENCE)) {
    const name = match[1] ?? ''
    if (!context.tokens.has(name)) {
      add(match.index, 'undefined-token', `${name} is not defined in tokens.css`)
    }
  }
  if (scope === 'design') {
    return findings
  }

  for (const match of text.matchAll(HEX_COLOUR)) {
    add(match.index, 'raw-colour', `${match[0]} is a raw colour. Use a colour token`)
  }
  for (const match of text.matchAll(COLOUR_FUNCTION)) {
    add(match.index, 'raw-colour', `${match[0]}...) is a raw colour. Use a colour token`)
  }
  const inCss = cssRegions(file, text)
  for (const match of text.matchAll(CSS_COLOUR)) {
    const value = (match[2] ?? '').trim()
    if (!inCss(match.index)) {
      continue
    }
    if (!USES_TOKEN.test(value) && !NEUTRAL_VALUE.test(value) && !isAlreadyReported(value)) {
      add(match.index, 'raw-colour', `"${match[1]}: ${value}" does not use a colour token`)
    }
  }
  for (const match of text.matchAll(RAW_SIZE)) {
    if (!ALLOWED_SIZES.has(match[0])) {
      add(match.index, 'raw-size', `${match[0]} is a raw size. Use a token or the spacing scale`)
    }
  }
  for (const pattern of [CSS_FONT, JS_FONT]) {
    for (const match of text.matchAll(pattern)) {
      const value = (match[2] ?? '').trim()
      if (pattern === CSS_FONT && !inCss(match.index)) {
        continue
      }
      if (!USES_TOKEN.test(value) && !NEUTRAL_VALUE.test(value)) {
        add(match.index, 'raw-font', `"${match[1]}: ${value}" does not use a token`)
      }
    }
  }
  for (const pattern of [ARBITRARY_VALUE, ARBITRARY_PROPERTY, ARBITRARY_VARIABLE]) {
    for (const match of text.matchAll(pattern)) {
      add(match.index, 'arbitrary-value', `${match[0]} is a one-off value. Use a token-based class`)
    }
  }
  for (const match of text.matchAll(FRACTIONAL_SPACING)) {
    add(
      match.index,
      'off-scale',
      `${match[0]} is off the spacing scale. Use half a step (0.5, which is 2 px) or whole steps`,
    )
  }
  for (const match of text.matchAll(NUMERIC_LINE_HEIGHT)) {
    add(match.index, 'off-scale', `${match[0]} is a one-off line height. Use a line height token`)
  }
  for (const match of text.matchAll(NUMERIC_DURATION)) {
    add(
      match.index,
      'off-scale',
      `${match[0]} is a one-off duration. Use duration-fast or duration-base`,
    )
  }
  if (file.endsWith('.vue')) {
    for (const { name, index } of classesIn(text)) {
      if (!context.isKnownClass(name)) {
        add(index, 'unknown-class', `${name} is not a class of the theme. Use a token-based class`)
      }
    }
  }
  return findings.sort((a, b) => a.line - b.line)
}

/**
 * Return every class name written in the class attributes of a Vue template.
 *
 * Static `class="..."` attributes are split at spaces. For bound `:class`
 * attributes the quoted texts inside the expression are split the same way.
 *
 * @param text - The content of a .vue file.
 */
export function classesIn(text: string): { name: string; index: number }[] {
  const classes: { name: string; index: number }[] = []
  const collect = (list: string, offset: number): void => {
    for (const word of list.matchAll(/\S+/g)) {
      classes.push({ name: word[0], index: offset + word.index })
    }
  }
  for (const match of text.matchAll(STATIC_CLASS)) {
    collect(match[1] ?? '', match.index + 'class="'.length)
  }
  for (const match of text.matchAll(BOUND_CLASS)) {
    const expression = match[1] ?? ''
    const start = match.index + match[0].indexOf('"') + 1
    for (const quoted of expression.matchAll(QUOTED)) {
      collect(quoted[1] ?? quoted[2] ?? '', start + quoted.index + 1)
    }
  }
  return classes
}

/**
 * Return a test for "is this position inside CSS": a stylesheet, a style block or a style attribute.
 * Declaration rules apply only there, so an object key named `color` in a script is not a finding.
 */
function cssRegions(file: string, text: string): (index: number) => boolean {
  if (file.endsWith('.css')) {
    return () => true
  }
  if (file.endsWith('.ts')) {
    return () => false
  }
  const regions = [...text.matchAll(STYLE_BLOCK), ...text.matchAll(STYLE_ATTRIBUTE)].map(
    (match) => [match.index, match.index + match[0].length] as const,
  )
  return (index) => regions.some(([start, end]) => index >= start && index < end)
}

function isAlreadyReported(value: string): boolean {
  HEX_COLOUR.lastIndex = 0
  COLOUR_FUNCTION.lastIndex = 0
  return HEX_COLOUR.test(value) || COLOUR_FUNCTION.test(value)
}

function lineAt(text: string, index: number): number {
  let line = 1
  for (let position = 0; position < index; position++) {
    if (text.charCodeAt(position) === 10) {
      line++
    }
  }
  return line
}
