/**
 * The entry point of the interface: theme, clock, stores, texts, pages, then the app.
 */
import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import { applyTheme } from './design'
import { startClock } from './format/clock'
import { i18n } from './i18n'
import { createAppRouter } from './router'

// Until the Theme setting exists (milestone M7) the app follows the system (R-PL-05).
applyTheme('system')

// Texts such as "checked 2 min ago" follow the clock.
startClock()

createApp(App).use(createPinia()).use(i18n).use(createAppRouter()).mount('#app')
