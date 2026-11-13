/**
 * Sets up vue-i18n with the English texts (R-PL-06).
 *
 * The UI language is English only in V1. Adding a language later means adding
 * a file next to en.ts and registering it here.
 */
import { createI18n } from 'vue-i18n'

import { en } from './en'

export const i18n = createI18n({
  legacy: false,
  locale: 'en',
  fallbackLocale: 'en',
  messages: { en },
})
