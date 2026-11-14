/**
 * The user text of an error code (R-ER-01, R-ER-02): what happened, what
 * yt-mirror is doing about it, and what the user can do. The texts are in
 * en.ts under the key of the code. A code without texts of its own gets one
 * plain sentence. The technical details arrive with milestone M7.
 */
import { useI18n } from 'vue-i18n'

import type { ErrorCode } from '@/api/client'

/** The three sentences of an error. The last two are empty for a code without texts. */
export interface ErrorTexts {
  happened: string
  doing: string
  action: string
}

/** Returns a function that gives the texts of an error code. */
export function useErrorTexts(): (code: ErrorCode) => ErrorTexts {
  const { t, te } = useI18n()
  return (code) => {
    const key = `errors.${code.toLowerCase()}`
    if (!te(`${key}.happened`)) {
      return { happened: t('error.unknown'), doing: '', action: '' }
    }
    return { happened: t(`${key}.happened`), doing: t(`${key}.doing`), action: t(`${key}.action`) }
  }
}
