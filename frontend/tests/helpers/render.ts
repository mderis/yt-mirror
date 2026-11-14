/** Renders a component the way the app does: with stores, pages and the English texts. */
import { render, type RenderResult } from '@testing-library/vue'
import { createPinia, setActivePinia } from 'pinia'
import type { Component } from 'vue'
import { createMemoryHistory, type Router } from 'vue-router'

import { i18n } from '@/i18n'
import { createAppRouter } from '@/router'

/**
 * Render a component with everything the app gives it.
 *
 * @param route The address the window is at. The pages of the app live in memory here.
 */
export function renderWithApp(
  component: Component,
  route = '/',
): RenderResult & { router: Router } {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createAppRouter(createMemoryHistory())
  void router.push(route)
  const result = render(component, { global: { plugins: [pinia, i18n, router] } })
  return Object.assign(result, { router })
}
