/** Renders a component the way the app does: with stores and the English texts. */
import { render, type RenderResult } from '@testing-library/vue'
import { createPinia, setActivePinia } from 'pinia'
import type { Component } from 'vue'

import { i18n } from '@/i18n'

export function renderWithApp(component: Component): RenderResult {
  const pinia = createPinia()
  setActivePinia(pinia)
  return render(component, { global: { plugins: [pinia, i18n] } })
}
