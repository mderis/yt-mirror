/**
 * The entry point of the theme preview page (R-TH-08). Development only:
 * open /theme-preview.html on the development server of `./start --dev`.
 */
import { createApp } from 'vue'

import { i18n } from '@/i18n'

import { applyTheme } from '..'
import ThemePreview from './ThemePreview.vue'

applyTheme('system')

createApp(ThemePreview).use(i18n).mount('#app')
