/**
 * The entry point of the interface: theme, stores, texts, then the app.
 */
import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import { applyTheme } from './design'
import { i18n } from './i18n'

// Until the Theme setting exists (milestone M7) the app follows the system (R-PL-05).
applyTheme('system')

createApp(App).use(createPinia()).use(i18n).mount('#app')
