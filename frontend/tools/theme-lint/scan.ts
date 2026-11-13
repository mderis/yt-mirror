/**
 * Runs the theme lint over the source tree. Implements R-TH-06 and R-TH-09.
 *
 * Files in src/design/ (the theme center) are checked only for references to
 * undefined tokens. Every other source file must use nothing but tokens.
 * Class names are checked with Tailwind's own engine, loaded with the preset
 * of the theme center, so "is this class defined" has exactly one answer.
 */
import { readdirSync, readFileSync } from 'node:fs'
import { dirname, join, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

// Tailwind does not offer a stable API for this yet. The version is pinned by package-lock.json.
import { __unstable__loadDesignSystem as loadDesignSystem } from '@tailwindcss/node'

import { allTokenNames, parseTokens } from '../../src/design/tokens.ts'
import { checkText, type Finding, type LintContext, type Scope } from './rules.ts'

export const FRONTEND_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..')
const DESIGN_DIR = join('src', 'design')
const CHECKED_EXTENSIONS = ['.vue', '.ts', '.css', '.html']
const ENTRY_PAGES = ['index.html', 'theme-preview.html']
// Third-party font declarations are kept as delivered and contain no tokens.
const SKIPPED_DIRS = [join(DESIGN_DIR, 'fonts')]

/**
 * Build what the rules need to know: the defined tokens and the class check.
 *
 * @param frontendDir - The frontend folder. Default: this one.
 */
export async function loadContext(frontendDir: string = FRONTEND_DIR): Promise<LintContext> {
  const designDir = join(frontendDir, DESIGN_DIR)
  const tokens = allTokenNames(parseTokens(readFileSync(join(designDir, 'tokens.css'), 'utf8')))
  const stylesheet = readFileSync(join(designDir, 'index.css'), 'utf8')
  const designSystem = await loadDesignSystem(stylesheet, { base: designDir })
  const known = new Map<string, boolean>()
  return {
    tokens,
    isKnownClass: (name) => {
      let answer = known.get(name)
      if (answer === undefined) {
        answer = designSystem.candidatesToCss([name])[0] !== null
        known.set(name, answer)
      }
      return answer
    },
  }
}

/**
 * Return the source files the lint checks, as paths relative to the frontend folder.
 *
 * @param frontendDir - The frontend folder. Default: this one.
 */
export function sourceFiles(frontendDir: string = FRONTEND_DIR): string[] {
  const found = readdirSync(join(frontendDir, 'src'), { recursive: true, encoding: 'utf8' })
    .map((path) => join('src', path))
    .filter((path) => CHECKED_EXTENSIONS.some((extension) => path.endsWith(extension)))
    .filter((path) => !SKIPPED_DIRS.some((dir) => path.startsWith(dir + sep)))
  return [...ENTRY_PAGES, ...found].sort()
}

/**
 * Return whether a file belongs to the theme center or to the rest of the code.
 *
 * @param path - A path relative to the frontend folder.
 */
export function scopeOf(path: string): Scope {
  return path.startsWith(DESIGN_DIR + sep) ? 'design' : 'code'
}

/**
 * Check every source file.
 *
 * @param frontendDir - The frontend folder. Default: this one.
 * @returns All findings, by file and line.
 */
export async function lintSources(frontendDir: string = FRONTEND_DIR): Promise<Finding[]> {
  const context = await loadContext(frontendDir)
  return sourceFiles(frontendDir).flatMap((path) => {
    const text = readFileSync(join(frontendDir, path), 'utf8')
    return checkText(relative('.', join(frontendDir, path)) || path, text, scopeOf(path), context)
  })
}
