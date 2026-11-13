import { describe, expect, it } from 'vitest'

import type { ErrorCode } from '@/api/client'
import { en } from '@/i18n/en'

import { read, REPO_ROOT } from '../helpers/files'

describe('the user texts of error codes', () => {
  it('R-ER-04, R-ER-01: the unreachable server has its three texts under the key of its code', () => {
    const code: ErrorCode = 'LOCAL_SERVER_UNREACHABLE'
    const texts = en.errors[code.toLowerCase() as keyof typeof en.errors]

    expect(Object.keys(texts)).toEqual(['happened', 'doing', 'action'])
    for (const text of Object.values(texts)) {
      expect(text.length).toBeGreaterThan(10)
    }
  })

  it('R-ER-02: every code that has user text is a code the backend defines', () => {
    const backend = read(REPO_ROOT, 'backend', 'ytmirror', 'core', 'errors.py')
    const defined = [...backend.matchAll(/^ {4}([A-Z_]+) = "\1"$/gm)].map((match) => match[1])

    expect(defined).toContain('LOCAL_SERVER_UNREACHABLE')
    for (const key of Object.keys(en.errors)) {
      expect(defined, key).toContain(key.toUpperCase())
    }
  })
})
