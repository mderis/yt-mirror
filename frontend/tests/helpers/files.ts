/** Reads files of the repository in tests that check the real source tree. */
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

export const FRONTEND_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..')
export const DESIGN_DIR = join(FRONTEND_DIR, 'src', 'design')
export const REPO_ROOT = resolve(FRONTEND_DIR, '..')

export function read(...parts: string[]): string {
  return readFileSync(join(...parts), 'utf8')
}

export function exists(...parts: string[]): boolean {
  return existsSync(join(...parts))
}

export function list(...parts: string[]): string[] {
  return readdirSync(join(...parts)).sort()
}
